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
import worker

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

class Uptime(worker.Worker):
    hours = minutes = seconds = total = 0
    def __init__(self):
        self.begin = time.time()
        super(Uptime, self).__init__()

    def as_dict(self):
        return dict(hours=self.hours,
                    minutes=self.minutes,
                    seconds=self.seconds)

    def work(self):
        self.total = time.time() - self.begin
        self.hours = int(self.total / 3600)
        hrSecs = self.hours * 3600
        self.minutes = int((self.total - hrSecs) / 60)
        self.seconds = int(self.total - hrSecs - (self.minutes * 60))

class OBC(worker.Worker):
    modes = TelemetryMsg.modes
    mode_preflight  = TelemetryMsg.mode_preflight
    mode_ascent     = TelemetryMsg.mode_ascent
    mode_descent    = TelemetryMsg.mode_descent
    mode_landed     = TelemetryMsg.mode_landed

    worker_interval = 5.0

    def __init__(self, radio_type=radio.Radio):
        self.uptime = Uptime()
        super(OBC, self).__init__()
        self.telemetry = {}
        self.mode = self.mode_preflight
        self.log = logging.getLogger('obc')
        self.sys = System(self)
        self.radio = radio_type(handler=self.handle_message)
        self.screen = screen.Screen(self)
        self.droid = droid.Droid(self)
        self.gps = gps.GPS()
        self.dht22 = temperature.DHT22()
        self.ds18b20 = temperature.DS18B20()
        self.jobs = (self.uptime, self.sys, self.gps, self.dht22, self.ds18b20,
                     self.radio, self.droid, self.screen)

    def started(self):
        for job in self.jobs:
            job.start()

        self.log.info('OBC booted in %0.2f seconds', time.time() - self.uptime.begin)

    def stopped(self):
        for job in self.jobs:
            job.stop()

    def __del__(self):
        self.stop()

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

    def handle_message(self, msg):
        if isinstance(msg, (proto.StartPhotoDataMsg, proto.StopPhotoDataMsg,
                            proto.SendTextMsg, proto.AddPhoneNumberMsg)):
            self.droid.send_message(msg)

    def send_message(self, msg, src='obc', **kwargs):
        if not isinstance(msg, proto.Msg):
            msg = msg.from_data(**kwargs)

        self.log.message(msg)
        self.radio.write(msg.as_buffer())

    def work(self):
        for message in self.droid.telemetry:
            self.send_message(message)

        self.send_message(TelemetryMsg,
                          uptime=int(self.uptime.total),
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

class System(worker.Worker):
    worker_interval = 5.0
    cpu_usage = 0
    free_mem = 0
    total_procs = 0
    total_mem = 0
    uptime = 0

    helper = os.path.join(this_dir, 'system', 'sys_helper.sh')

    def __init__(self, obc):
        super(System, self).__init__()
        self.time_set = False
        self.obc = obc

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
        new_begin = gps_time + timedelta(hours=self.obc.uptime.hours,
                                         minutes=self.obc.uptime.minutes,
                                         seconds=self.obc.uptime.seconds)

        self.obc.uptime.begin = calendar.timegm(new_begin.utctimetuple())

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

    def work(self):
        self.update_stats()
        #self.maybe_update_time()
