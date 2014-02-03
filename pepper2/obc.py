import json
import logging
import os
import subprocess
import sys
import time

import gevent
import pynmea

import gps
import droid
import radio
import screen
import temp_sensor

this_dir = os.path.abspath(os.path.dirname(__file__))

class Timer(object):
    def __init__(self, interval, fn):
        self.log = logging.getLogger('timer')
        self.interval = interval
        self.fn = fn

    def start(self):
        gevent.spawn_later(self.interval, self)

    def __call__(self):
        self.log.debug('calling ' + self.fn.__name__)
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
        self.log = logging.getLogger('obc')
        self.sys = System()
        self.gps = gps.GPS()
        self.radio = radio_type(self)
        self.screen = screen.Screen(self)
        self.droid = droid.Droid(self)
        self.temp = temp_sensor.TempSensor()

        self.start_timers((self.sensor_interval, self.sensor_update),
                          (self.sys_interval, self.sys_update),
                          (self.telemetry_interval, self.send_all_telemetry))

        self.log.info('OBC booted in %0.2f seconds', time.time() - self.begin)

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
        ppr2_nmea += '*' + pynmea.utils.checksum_calc(ppr2_nmea)
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
