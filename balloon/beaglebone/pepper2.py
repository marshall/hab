import collections
from datetime import datetime, timedelta
import logging
import logging.config
import math
import os
import subprocess
import sys
import time
import Queue

import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.UART as UART
from pynmea import nmea, utils
import serial
import ssd1306

import droid
import screen

this_dir = os.path.abspath(os.path.dirname(__file__))
logging.config.fileConfig(os.path.join(this_dir, 'logging.conf'))

class OBCTimer(object):
    def __init__(self, interval, fn):
        self.last_call = 0
        self.interval = interval
        self.fn = fn

    def tick(self):
        if time.time() - self.last_call >= self.interval:
            self.fn()
            self.last_call = time.time()

class OBC(object):
    modes = ('preflight', 'ascent', 'descent', 'landed')
    mode_preflight  = 0
    mode_ascent     = 1
    mode_descent    = 2
    mode_landed     = 3

    sensor_interval         = 0.3
    telemetry_interval     = 5
    def __init__(self):
        self.begin = time.time()
        self.mode = self.mode_preflight
        self.cpu_usage = 0
        self.free_mem = 0
        self.timers = [ OBCTimer(self.sensor_interval, self.sensor_update),
                        OBCTimer(self.telemetry_interval, self.send_all_telemetry) ]
        self.logger = logging.getLogger('OBC')
        self.gps = GPS()
        self.screen = screen.Screen(self)
        self.droid = droid.Droid(self)
        self.update_main_interval()
        self.telemetry_queue = Queue.Queue(10)
        self.logger.info('OBC booted in %0.2f seconds', time.time() - self.begin)

    def update_main_interval(self):
        self.main_interval = min([t.interval for t in self.timers])

    def get_uptime(self):
        return dict(hours=self.uptime_hr, minutes=self.uptime_min,
                    seconds=self.uptime_sec)

    def main_loop(self):
        while True:
            for timer in self.timers:
                timer.tick()

            time.sleep(self.main_interval)

    def sys_update(self):
        now = time.time()
        uptime = now - self.begin
        self.uptime_hr = int(uptime / 3600)
        hrSecs = self.uptime_hr * 3600
        self.uptime_min = int((uptime - hrSecs) / 60)
        self.uptime_sec = int(uptime - hrSecs - (self.uptime_min * 60))

        stats = subprocess.check_output(
            'top -bn 1 | awk \'BEGIN{FS="[ \t%]+"} NR==3{ print 100-$8 } NR==4{ print $6 }\'',
            shell=True)

        lines = stats.splitlines()
        self.cpu_usage = float(lines[0].strip())
        if len(lines) > 1:
            self.free_mem = int(lines[1].strip().replace('k', '')) / 1024.0

    def sensor_update(self):
        self.sys_update()
        self.gps.update()
        self.maybe_update_mode()

    def maybe_update_mode(self):
        if len(self.gps.fixes) != self.gps.fix_count:
            return

        fixes = self.gps.fixes
        altitude_diff = fixes[-1][2] - fixes[0][2]
        target_velocity = 0.001 * len(fixes)

        if self.mode == self.mode_preflight:
            if altitude_diff >= target_velocity: # climbing greater than 1m/s
                self.mode = self.mode_ascent
                self.on_ascent()

        elif self.mode == self.mode_ascent:
            if altitude_diff <= -target_velocity: # falling greater than 1m/s
                self.mode = self.mode_descent
                self.on_descent()

        elif self.mode == self.mode_descent:
            if altitude_diff > -target_velocity and altitude_diff < target_velocity:
                self.mode = self.mode_landed
                self.on_landed()

    def on_ascent(self):
        pass

    def on_descent(self):
        pass

    def on_landed(self):
        pass

    def build_nmea(self, type, sentence):
        ppr2_nmea = '$PPR2%s,%s' % (type, sentence)
        ppr2_nmea += '*' + utils.checksum_calc(ppr2_nmea)
        return ppr2_nmea

    def send_all_telemetry(self):
        for telemetry_list in (self.droid.telemetry, self.gps.telemetry):
            for telemetry in telemetry_list:
                self.send_raw(telemetry)

        self.send_raw(self.build_nmea('T', '%d,%s,%+03.2f,%+03.2f' % ( \
                                      time.time() - self.begin,
                                      self.modes[self.mode],
                                      0,   # TODO temperature
                                      0))) # TODO humidity

        try:
            while True:
                self.send_raw(self.telemetry_queue.get(False))
                self.telemetry_queue.task_done()
        except Queue.Empty, e:
            pass

    def queue_telemetry(self, raw):
        self.telemetry_queue.put(raw)

    def send_raw(self, msg):
        self.logger.info('TELEMETRY %s', msg)

    def start_timers(self, *timers):
        obc_timers = []
        for timer in timers:
            obc_timer = OBCTimer(*timer)
            obc_timers.append(obc_timer)
            self.timers.append(obc_timer)

        self.update_main_interval()
        return obc_timers

    def stop_timers(self, timers):
        for timer in timers:
            self.timers.remove(timer)

        self.update_main_interval()

class GPS(object):
    uart = 'UART1'
    port = '/dev/ttyO1'
    baud = 9600
    fix_count = 5

    init_sentences = (
        '$PMTK220,1000*1F', # Update @ 1Hz
        '$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28') # Output RMC and GGA only

    def __init__(self):
        self.logger = logging.getLogger('GPS')
        self.latitude = self.longitude = self.altitude = self.quality = 0
        self.gpgga = self.gprmc = None
        self.fixes = collections.deque([], self.fix_count)

        self.logger.debug('setting up')
        UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=0.25)
        time.sleep(0.01) # 10 ms
        for sentence in self.init_sentences:
            self.serial.write(sentence + '\r\n')

    def update(self):
        line = self.serial.readline()
        if not line:
            return

        sentence = nmea.parse_sentence(line)

        if isinstance(sentence, nmea.GPGGA):
            self.gpgga = line
        elif isinstance(sentence, nmea.GPRMC):
            self.gprmc = line

        if not isinstance(sentence, nmea.GPGGA):
            return

        def nmea2float(value, dir, negative_dir):
            fval = math.floor(value / 100.0)
            fval += (value - (fval * 100)) / 60
            if dir == negative_dir:
                fval *= -1
            return fval

        if len(sentence.latitude) > 0:
            self.latitude = nmea2float(float(sentence.latitude),
                                       sentence.lat_direction, 'S')
        if len(sentence.longitude) > 0:
            self.longitude = nmea2float(float(sentence.longitude),
                                        sentence.lon_direction, 'W')

        if len(sentence.antenna_altitude) > 0:
            self.altitude = float(sentence.antenna_altitude) / 1000.0

        self.quality = int(sentence.gps_qual)
        self.fixes.append((self.latitude, self.longitude, self.altitude, self.quality))

    @property
    def telemetry(self):
        t = []
        if self.gprmc:
            t.append(self.gprmc)
        if self.gpgga:
            t.append(self.gpgga)
        return t

if __name__ == '__main__':
    OBC().main_loop()
