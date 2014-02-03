import gevent

import argparse
import collections
from datetime import datetime, timedelta
import json
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
import radio
import screen

this_dir = os.path.abspath(os.path.dirname(__file__))
logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                    level=logging.INFO)

class Timer(object):
    def __init__(self, interval, fn):
        self.logger = logging.getLogger('timer')
        self.interval = interval
        self.fn = fn

    def start(self):
        gevent.spawn_later(self.interval, self)

    def __call__(self):
        self.logger.debug('calling ' + self.fn.__name__)
        self.fn()
        gevent.spawn_later(self.interval, self)

class OBC(object):
    modes = ('preflight', 'ascent', 'descent', 'landed')
    mode_preflight  = 0
    mode_ascent     = 1
    mode_descent    = 2
    mode_landed     = 3

    sensor_interval        = 0.3
    sys_interval           = 1.0
    telemetry_interval     = 5.0

    telemetry_format = '{uptime:0.0f},{mode},{sys.cpu_usage:02.1f},' \
                       '{sys.free_mem_mb:02.1f},{temp.fahrenheit:+0.1f}F,' \
                       '{temp.humidity:+0.1f}'

    def __init__(self, radio_type=radio.Radio):
        self.begin = time.time()
        self.uptime_hr = self.uptime_min = self.uptime_sec = 0
        self.telemetry = {}
        self.timers = []
        self.mode = self.mode_preflight
        self.logger = logging.getLogger('obc')
        self.sys = System()
        self.gps = GPS()
        self.radio = radio_type(self)
        self.screen = screen.Screen(self)
        self.droid = droid.Droid(self)
        self.temp = TempSensor()

        self.start_timers((self.sensor_interval, self.sensor_update),
                          (self.sys_interval, self.sys_update),
                          (self.telemetry_interval, self.send_all_telemetry))

        self.logger.info('OBC booted in %0.2f seconds', time.time() - self.begin)

    def get_uptime(self):
        return dict(hours=self.uptime_hr, minutes=self.uptime_min,
                    seconds=self.uptime_sec)

    def main_loop(self):
        while True:
            gevent.sleep(5)

    def sys_update(self):
        now = time.time()
        uptime = now - self.begin
        self.uptime_hr = int(uptime / 3600)
        hrSecs = self.uptime_hr * 3600
        self.uptime_min = int((uptime - hrSecs) / 60)
        self.uptime_sec = int(uptime - hrSecs - (self.uptime_min * 60))
        self.sys.update()

    def sensor_update(self):
        self.gps.update()
        self.temp.update()
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
                self.radio.write_line(telemetry)

        sentence = self.telemetry_format.format(uptime=time.time() - self.begin,
                                                mode=self.modes[self.mode],
                                                sys=self.sys,
                                                temp=self.temp)
        self.radio.write_line(self.build_nmea('T', sentence))

    def start_timers(self, *timers):
        obc_timers = []
        for timer in timers:
            obc_timer = Timer(*timer)
            obc_timer.start()
            self.timers.append(obc_timer)

class System(object):
    def __init__(self):
        self.helper = os.path.join(this_dir, 'sys_helper.sh')
        for key, val in dict(uptime=0, total_procs=0, cpu_usage=0,
                total_mem=0, free_mem=0).iteritems():
            setattr(self, key, val)

    def update_stats(self):
        try:
            result = subprocess.check_output([self.helper, 'get_stats'])
            data = json.loads(result)
            if not data:
                return

            for key, val in data.iteritems():
                setattr(self, key, val)
        except subprocess.CalledProcessError, e:
            pass

    def set_hwclock(self, date_str):
        try:
            subprocess.check_output([self.helper, date_str])
            return True
        except subprocess.CalledProcessError, e:
            return False

    @property
    def free_mem_mb(self):
        return self.free_mem / 1024.0

    def update(self):
        self.update_stats()

class GPS(object):
    uart = 'UART1'
    port = '/dev/ttyO1'
    baud = 9600
    fix_count = 5

    init_sentences = (
        '$PMTK220,1000*1F', # Update @ 1Hz
        '$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28') # Output RMC and GGA only

    def __init__(self):
        self.logger = logging.getLogger('gps')
        self.latitude = self.longitude = self.altitude = self.quality = 0
        self.gpgga = self.gprmc = None
        self.fixes = collections.deque([], self.fix_count)

        self.logger.debug('setting up')
        UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=0.25)
        gevent.sleep(0.01) # 10 ms
        for sentence in self.init_sentences:
            self.serial.write(sentence + '\r\n')

    def update(self):
        #gevent.socket.wait_read(self.serial.fileno())
        line = self.serial.readline()
        if not line:
            return

        sentence = nmea.parse_sentence(line)

        if isinstance(sentence, nmea.GPGGA):
            self.gpgga = line.strip()
        elif isinstance(sentence, nmea.GPRMC):
            self.gprmc = line.strip()

        if not isinstance(sentence, nmea.GPGGA):
            return

        self.logger.debug('Fix: %s', line)
        def nmea2float(value, dir, negative_dir):
            fval = math.floor(value / 100.0)
            fval += (value - (fval * 100)) / 60
            if dir == negative_dir:
                fval *= -1
            return fval

        self.update_timestamp(sentence.timestamp)

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

    def update_timestamp(self, timestamp):
        if len(timestamp) < 5:
            return

        ts_hr, ts_min, ts_sec = int(timestamp[0:2]), int(timestamp[2:4]), float(timestamp[4:])
        self.logger.debug('timestamp = %d:%d:%0.2f', ts_hr, ts_min, ts_sec)

    @property
    def telemetry(self):
        t = []
        if self.gprmc:
            t.append(self.gprmc)
        if self.gpgga:
            t.append(self.gpgga)
        return t

class TempSensor(object):
    def __init__(self):
        self.logger = logging.getLogger('temp')
        self.celsius = 0
        self.humidity = 0
        self.kmod_loaded = False
        self.check_kernel_module()

    def check_kernel_module(self):
        if not os.path.exists('/proc/modules'):
            return

        modules = open('/proc/modules', 'rt').read()
        for line in modules.splitlines():
            if line.startswith('dht22'):
                self.kmod_loaded = True
                break

        if not self.kmod_loaded:
            self.load_kernel_module()

    def load_kernel_module(self):
        kmod_path = os.path.join(this_dir, 'dht22', 'dht22.ko')
        try:
            subprocess.check_call(['insmod', kmod_path])
            self.kmod_loaded = True
        except subprocess.CalledProcessError, e:
            self.logger.error('Unable to install dht22 kernel module')

    def read_sysfs_file(self, path, tries=5):
        while tries > 0:
            try:
                f = open(path, 'r')
                data = f.readline()
                f.close()
                return data
            except Exception, e:
                tries -= 1

        return None

    def update(self):
        t = self.read_sysfs_file('/sys/devices/platform/dht22/temp')
        h = self.read_sysfs_file('/sys/devices/platform/dht22/humidity')

        if t:
            self.celsius = int(t) / 1000.0
        if h:
            self.humidity = int(h) / 1000.0

    @property
    def fahrenheit(self):
        return 1.8 * self.celsius + 32

    @property
    def dew_point(self):
        a0 = 373.15 / (273.15 + self.celsius)
        dew_sum = -7.90298 * (a0 - 1)
        dew_sum += 5.02808 * math.log10(a0)
        dew_sum += -1.3816e-7 * (pow(10, (11.344*(1-1/a0)))-1)
        dew_sum += 8.1328e-3 * (pow(10,(-3.49149*(a0-1)))-1)
        dew_sum += math.log10(1013.246)
        vp = pow(10, dew_sum - 3) * self.humidity
        t = math.log(vp / 0.61078)
        return (241.88 * t) / (17.558 - t)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tcp', action='store_true', default=False)
    args = parser.parse_args()

    radio_type = radio.TCPRadio if args.tcp else radio.Radio
    OBC(radio_type=radio_type).main_loop()

if __name__ == '__main__':
    main()
