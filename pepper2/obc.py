import calendar
from datetime import datetime, timedelta
import json
import logging
import os
import subprocess
import sys
import time

import gevent
import pynmea

import droid
import gps
import proto
from proto import TelemetryMsg, LocationMsg
import radio
import screen
import temperature

this_dir = os.path.abspath(os.path.dirname(__file__))

class Timer(object):
    def __init__(self, interval, fn):
        self.log = logging.getLogger('timer')
        self.interval = interval
        self.fn = fn
        self.running = False

    def start(self):
        self.running = True
        gevent.spawn_later(self.interval, self)

    def stop(self):
        self.running = False

    def __call__(self):
        if not self.running:
            return

        self.fn()
        gevent.spawn_later(self.interval, self)

class OBC(object):
    modes = TelemetryMsg.modes
    mode_preflight  = TelemetryMsg.mode_preflight
    mode_ascent     = TelemetryMsg.mode_ascent
    mode_descent    = TelemetryMsg.mode_descent
    mode_landed     = TelemetryMsg.mode_landed

    sensor_interval        = 0.3
    sys_interval           = 1.0
    msg_interval           = 5.0

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
        self.sys = System(self)
        self.radio = radio_type(self)
        self.screen = screen.Screen(self)
        self.droid = droid.Droid(self)
        self.gps = gps.GPS()
        self.dht22 = temperature.DHT22()
        self.ds18b20 = temperature.DS18B20()
        self.running = False

        self.start_timers((self.sys_interval, self.sys_update),
                          (self.msg_interval, self.send_all_messages))
        self.log.info('OBC booted in %0.2f seconds', time.time() - self.begin)

    def shutdown(self):
        self.running = False
        for timer in self.timers:
            timer.stop()

        self.droid.shutdown()
        self.radio.shutdown()

    def __del__(self):
        self.shutdown()

    def get_uptime(self):
        return dict(hours=self.uptime_hr, minutes=self.uptime_min,
                    seconds=self.uptime_sec)

    def main_loop(self):
        self.running = True
        while self.running:
            gevent.sleep(2)

    def sys_update(self):
        now = time.time()
        uptime = now - self.begin
        self.uptime_hr = int(uptime / 3600)
        hrSecs = self.uptime_hr * 3600
        self.uptime_min = int((uptime - hrSecs) / 60)
        self.uptime_sec = int(uptime - hrSecs - (self.uptime_min * 60))
        self.sys.update()

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

    def send_message(self, msg, src='obc', **kwargs):
        if not isinstance(msg, proto.Msg):
            msg = msg.from_data(**kwargs)

        self.log.message(msg)
        self.radio.write(msg.as_buffer())

    def send_all_messages(self):
        for message in self.droid.telemetry:
            self.send_message(message)

        self.send_message(TelemetryMsg,
                          uptime=int(time.time() - self.begin),
                          mode=self.mode,
                          cpu_usage=int(self.sys.cpu_usage),
                          free_mem=int(self.sys.free_mem/1024),
                          int_temperature=round(self.dht22.temp, 2),
                          int_humidity=round(self.dht22.humidity, 2),
                          ext_temperature=round(self.ds18b20.temp, 2))

        self.send_message(LocationMsg,
                          latitude=self.gps.latitude,
                          longitude=self.gps.longitude,
                          altitude=self.gps.altitude,
                          quality=self.gps.quality,
                          satellites=self.gps.satellites,
                          speed=self.gps.speed)

    def start_timers(self, *timers):
        obc_timers = []
        for timer in timers:
            obc_timer = Timer(*timer)
            obc_timer.start()
            self.timers.append(obc_timer)

class System(object):
    def __init__(self, obc):
        self.time_set = False
        self.obc = obc
        self.log = logging.getLogger('sys')
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

    def maybe_update_time(self):
        if self.time_set:
            return

        if not self.obc.sensors.is_gps_time_valid():
            return

        gps_time = self.obc.sensors.gps_time
        self.time_set = self.set_time(gps_time.strftime('%Y-%m-%d'),
                                      gps_time.strftime('%H:%M:%S'))

        if not self.time_set:
            self.log.warning('Unable to set system time, will try again')
            return

        # we also need to reset the OBC uptime here..
        new_begin = gps_time + timedelta(hours=self.obc.uptime_hr,
                                         minutes=self.obc.uptime_min,
                                         seconds=self.obc.uptime_sec)

        self.obc.begin = calendar.timegm(new_begin.utctimetuple())

    def set_time(self, date_str, time_str):
        self.log.info('Updating system time: "%s" "%s"', date_str, time_str)

        try:
            subprocess.check_output([self.helper, 'set_time', date_str, time_str])
            return True
        except subprocess.CalledProcessError, e:
            return False

    @property
    def free_mem_mb(self):
        return self.free_mem / 1024.0

    def update(self):
        self.update_stats()
        #self.maybe_update_time()
