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

    sensor_interval      = 0.3
    oled_interval        = 1
    oled_switch_interval = 5
    telemetry_interval   = 5

    def __init__(self):
        self.begin = time.time()
        self.mode = self.mode_preflight
        self.cpu_usage = 0
        self.free_mem = 0
        self.logger = logging.getLogger('OBC')
        self.gps = GPS()
        self.oled = OLED(self)
        self.droid = droid.Droid(self)
        self.timers = [
            OBCTimer(self.sensor_interval, self.sensor_update),
            OBCTimer(self.oled_interval, self.oled.update),
            OBCTimer(self.telemetry_interval, self.send_all_telemetry),
            OBCTimer(self.oled_switch_interval, self.switch_info_screen)]
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

    def switch_info_screen(self):
        next = self.oled.screen + 1
        if next >= len(self.oled.screens):
            next = 0

        self.oled.switch_screen(next)

    def start_timer(self, timer):
        self.timers.append(timer)
        self.update_main_interval()

    def stop_timer(self, timer):
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

class Screen(object):
    def __init__(self, oled):
        self.oled = oled
        self.font_width = oled.oled.font.cols
        self.font_height = oled.oled.font.rows
        self.screen_height = oled.oled.rows
        self.in_buffer = False
        self.template_args = {}
        self.origin_x = self.origin_y = 0
        self.mini_stat_y = self.data_x = self.data_y = 0

    def do_draw(self, x, y):
        self.origin_x = x
        self.origin_y = y
        self.mini_stat_y = self.data_x = self.data_y = 0
        self.draw()

    def text_width(self, text, size=1, space=1):
        w = len(text) * self.font_width
        w *= size
        w += (len(text) - 1) * space
        return w

    def text_height(self, size=1):
        return self.font_height * size

    def draw_title(self, heading):
        heading_size = 2
        offset_y = 1
        line_size = 1
        padding = 2

        self.oled.draw_text(self.origin_x, self.origin_y + offset_y, heading, size=heading_size)
        heading_width = self.text_width(heading, size=heading_size)

        line_y = self.origin_y + offset_y + self.text_height(size=heading_size) + padding
        for x in range(self.origin_x, self.origin_x + heading_width):
            for y in range(0, line_size):
                self.oled.oled.draw_pixel(x, line_y + y, 1)

        right_line_x = self.origin_x + heading_width + padding
        for x in range(0, line_size):
            for y in range(self.origin_y, self.origin_y + self.screen_height):
                self.oled.oled.draw_pixel(right_line_x + x, y, 1)

        self.mini_stat_y = line_y + padding
        self.data_x = right_line_x + line_size + padding

    def draw_mini_stat(self, mini_stat):
        self.oled.draw_text(self.origin_x, self.mini_stat_y,
                            mini_stat % self.template_args, size=1)

    def draw_lines(self, lines, **kwargs):
        size = kwargs.get('size', 1)
        for line in lines:
            self.oled.draw_text(self.data_x,
                                self.origin_y + self.data_y,
                                line % self.template_args,
                                **kwargs)
            self.data_y += self.text_height(size=size)

class MainScreen(Screen):
    header = '%(current_time)s %(hours)02dh%(minutes)02dm%(seconds)02ds'
    lines  = ('AND:%(droid_bt)c RDO:%(radio)c GPS:%(gps_qual)s',
              'TMP:%(tmp)+02.2fF LAT:%(gps_lat)+02.1f',
              'LNG:%(gps_lng)+02.1f ALT:%(gps_alt)+02.1fK')

    def draw(self):
        self.draw_lines([self.header], invert=True)
        self.draw_lines(self.lines)

class SysScreen(Screen):
    lines = ('%(current_time)s',
             'CPU %(cpu_usage)02.1f%%',
             'MEM %(free_mem)dMB free',
             'UP  %(hours)02dh %(minutes)02dm %(seconds)02ds')

    def draw(self):
        self.draw_title('SYS')
        self.draw_lines(self.lines)

class GPSScreen(Screen):
    lines = ('QUAL %(gps_qual)s',
             'LAT  %(gps_lat)+02.5f',
             'LNG  %(gps_lng)+02.5f',
             'ALT  %(gps_alt)02.3fK')

    def draw(self):
        self.draw_title('GPS')
        self.draw_mini_stat('Q: %(gps_qual)s')
        self.draw_lines(self.lines)

class DroidScreen(Screen):
    # yeah, this is epic
    bitmap = (0b00000000100000000100000000,
              0b00000000011111111000000000,
              0b00000000111111111100000000,
              0b00000001111111111110000000,
              0b00000011101111110111000000,
              0b00000111111111111111100000,
              0b00000000000000000000000000,
              0b01100111111111111111100110,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b11110111111111111111101111,
              0b01100111111111111111100110,
              0b00000111111111111111100000,
              0b00000111111111111111100000,
              0b00000011111111111111000000,
              0b00000000111000011100000000,
              0b00000000111000011100000000,
              0b00000000111000011100000000,
              0b00000000111000011100000000,
              0b00000000111000011100000000)

    bitmap_width = 26
    bitmap_height = 24

    lines = ('BAT %(droid_battery)d%% CELL %(droid_cell)s',
             'PHOTOS %(droid_photos)d',
             'LAT %(droid_lat)+02.5f',
             'LNG %(droid_lng)+02.5f')

    def draw(self):
        for x in range(0, self.bitmap_width):
            for y in range(0, self.bitmap_height):
                line = self.bitmap[y]
                self.oled.oled.draw_pixel(self.origin_x + x, self.origin_y + y,
                                          line & (1 << x))

        self.oled.oled.draw_text2(self.origin_x + 1,
                                  self.origin_y + self.bitmap_height + 1,
                                  'BT:%(droid_bt)c' % self.template_args,
                                  size=1)

        padding = 2
        line_size = 1
        right_line_x = self.origin_x + self.bitmap_width + padding
        for x in range(0, line_size):
            for y in range(self.origin_y, self.origin_y + self.screen_height):
                self.oled.oled.draw_pixel(right_line_x + x, y, 1)

        self.data_x = right_line_x + line_size + padding
        self.draw_lines(self.lines)

class ScreenBuffer(object):
    scroll_interval = 0.01

    def __init__(self, oled, screens):
        self.oled = oled
        self.screen_height = oled.rows
        self.screens = screens
        for screen in screens:
            screen.in_buffer = True

        self.active = 0

    @property
    def inactive(self):
        return 1 if self.active == 0 else 0

    @property
    def active_screen(self):
        return self.screens[self.active]

    @property
    def inactive_screen(self):
        return self.screens[self.inactive]

    def switch_screen(self, screen):
        try:
            index = self.screens.index(screen)
            self.active = index
        except ValueError, e:
            # new screen
            self.active = self.inactive
            self.screens[self.active].in_buffer = False
            self.screens[self.active] = screen
            screen.in_buffer = True
            self.oled.clear_display()
            screen.do_draw(0, self.active * self.screen_height)
            self.oled.display()

        start_y = self.inactive * self.screen_height
        dest_y = self.active * self.screen_height
        lambda_y = 1 if self.inactive == 0 else -1

        # this takes over the main loop for smooth animation
        for y in range(start_y, dest_y + lambda_y, lambda_y):
            self.oled.command(self.oled.SET_START_LINE | y)
            time.sleep(self.scroll_interval)

    def draw(self):
        for i in range(len(self.screens)):
            self.screens[i].do_draw(0, i * self.screen_height)

class OLED(object):
    bus        = 1
    device     = 0
    reset_pin  = 'P9_13'
    dc_pin     = 'P9_15'

    def __init__(self, obc):
        self.logger = logging.getLogger('OLED')
        self.logger.debug('setting up')
        self.obc = obc
        self.screen = 0
        self.oled = ssd1306.SSD1306(bus=self.bus, device=self.device,
                                    reset_pin=self.reset_pin, dc_pin=self.dc_pin)
        self.screens = [SysScreen(self), GPSScreen(self), DroidScreen(self)]
        self.screen_buffer = ScreenBuffer(self.oled, self.screens[0:2])
        self.oled.begin()

    def yn(self, val):
        return 'Y' if val else 'N'

    def draw_text(self, x, y, text, **kwargs):
        if 'size' not in kwargs:
            kwargs['size'] = 1

        self.oled.draw_text2(x, y, text, **kwargs)

    def switch_screen(self, screen):
        self.screen_buffer.switch_screen(self.screens[screen])
        self.screen = screen

    def build_template_args(self):
        gps = self.obc.gps
        droid = self.obc.droid
        return dict(
            current_time=time.strftime('%m/%d %H:%M'),
            cpu_usage=self.obc.cpu_usage,
            free_mem=self.obc.free_mem,
            droid_bt=self.yn(droid.connected),
            droid_battery=droid.battery,
            droid_cell=self.yn(droid.radio),
            droid_photos=droid.photo_count,
            droid_lat=droid.latitude,
            droid_lng=droid.longitude,
            droid_alt=droid.altitude,
            radio=self.yn(False),
            tmp=0,
            gps_qual=gps.quality,
            gps_lat=gps.latitude,
            gps_lng=gps.longitude,
            gps_alt=gps.altitude,
            **self.obc.get_uptime())

    def update(self):
        template_args = self.build_template_args()
        self.oled.clear_display()

        for screen in self.screens:
            screen.template_args = template_args

        self.screen_buffer.draw()
        self.oled.display()

if __name__ == '__main__':
    OBC().main_loop()
