import datetime
import logging
import time

import ssd1306

class Screen(object):
    bus        = 1
    device     = 0
    reset_pin  = 'P9_13'
    dc_pin     = 'P9_15'

    update_interval = 1
    switch_interval = 5

    def __init__(self, obc):
        self.logger = logging.getLogger('screen')
        self.obc = obc
        self.panel = 0
        self.oled = ssd1306.SSD1306(bus=self.bus, device=self.device,
                                    reset_pin=self.reset_pin, dc_pin=self.dc_pin)

        self.panels = [SysPanel(self), GPSPanel(self), DroidPanel(self)]
        self.panel_buffer = PanelBuffer(self, self.panels[0:2])
        self.height = self.oled.rows
        self.font_width = self.oled.font.cols
        self.font_height = self.oled.font.rows

        self.oled.begin()
        self.timers = obc.start_timers((self.update_interval, self.update),
                                       (self.switch_interval, self.next_active_panel))

    def yn(self, val):
        return 'Y' if val else 'N'

    def clear_display(self):
        self.oled.clear_display()

    def display(self):
        self.oled.display()

    def draw_pixel(self, x, y, value):
        self.oled.draw_pixel(x, y, value)

    def draw_text(self, x, y, text, **kwargs):
        if 'size' not in kwargs:
            kwargs['size'] = 1

        self.oled.draw_text2(x, y, text, **kwargs)

    def set_start_line(self, y):
        self.oled.command(self.oled.SET_START_LINE | y)

    def next_active_panel(self):
        next = self.panel + 1
        if next >= len(self.panels):
            next = 0

        self.switch_panel(next)

    def switch_panel(self, panel):
        self.panel_buffer.switch_panel(self.panels[panel])
        self.panel = panel

    def build_template_args(self):
        gps = self.obc.gps
        droid = self.obc.droid
        sys = self.obc.sys
        '''args = self.obc.get_uptime()
        args.update(sys.get_stats())
        args.update(
            current_time=time.strftime('%m/%d %H:%M'),
            droid_bt=self.yn(droid.connected),
            droid_battery=droid.battery,
            droid_cell=self.yn(droid.radio),
            droid_photos=droid.photo_count,
            droid_lat=droid.latitude,
            droid_lng=droid.longitude,
            droid_alt=droid.altitude,
            radio=self.yn(False),
            temp=self.obc.temp.fahrenheit,
            humidity=self.obc.temp.humidity,
            gps_qual=gps.quality,
            gps_lat=gps.latitude,
            gps_lng=gps.longitude,
            gps_alt=gps.altitude)
        return args'''

        return dict(
            obc=self.obc,
            sys=self.obc.sys,
            gps=self.obc.gps,
            droid=self.obc.droid,
            temp=self.obc.temp,
            now=datetime.datetime.now())

    def update(self):
        template_args = self.build_template_args()

        self.oled.clear_display()
        for panel in self.panels:
            panel.template_args = template_args

        self.panel_buffer.draw()
        self.oled.display()

class Panel(object):
    def __init__(self, screen):
        self.screen = screen
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
        w = len(text) * self.screen.font_width
        w *= size
        w += (len(text) - 1) * space
        return w

    def text_height(self, size=1):
        return self.screen.font_height * size

    def draw_title(self, heading):
        heading_size = 2
        offset_y = 1
        line_size = 1
        padding = 2

        self.screen.draw_text(self.origin_x, self.origin_y + offset_y, heading, size=heading_size)
        heading_width = self.text_width(heading, size=heading_size)

        line_y = self.origin_y + offset_y + self.text_height(size=heading_size) + padding
        for x in range(self.origin_x, self.origin_x + heading_width):
            for y in range(0, line_size):
                self.screen.draw_pixel(x, line_y + y, 1)

        right_line_x = self.origin_x + heading_width + padding
        for x in range(0, line_size):
            for y in range(self.origin_y, self.origin_y + self.screen.height):
                self.screen.draw_pixel(right_line_x + x, y, 1)

        self.mini_stat_y = line_y + padding
        self.data_x = right_line_x + line_size + padding

    def draw_mini_stat(self, mini_stat):
        self.screen.draw_text(self.origin_x, self.mini_stat_y,
                              mini_stat.format(**self.template_args), size=1)

    def draw_lines(self, lines, **kwargs):
        size = kwargs.get('size', 1)
        for line in lines:
            self.screen.draw_text(self.data_x,
                                  self.origin_y + self.data_y,
                                  line.format(**self.template_args),
                                  **kwargs)
            self.data_y += self.text_height(size=size)

class MainPanel(Panel):
    header = '{now:%m/%d %H:%M} {obc.uptime_hr:02d}h{obc.uptime_min:02d}m{obc.uptime_sec:02d}s'
    lines = ('AND:{droid.connected:d} RDO:F GPS:{gps.quality}',
             'TMP:{temp.fahrenheit:+02.2f}F LAT:{gps.latitude:+02.1f}',
             'LNG:{gps.longitude:+02.1f} ALT:{gps.altitude:+02.1f}K')

    #header = '%(current_time)s %(hours)02dh%(minutes)02dm%(seconds)02ds'
    #lines  = ('AND:%(droid_bt)c RDO:%(radio)c GPS:%(gps_qual)s',
    #          'TMP:%(temp)+02.2fF LAT:%(gps_lat)+02.1f',
    #          'LNG:%(gps_lng)+02.1f ALT:%(gps_alt)+02.1fK')

    def draw(self):
        self.draw_lines([self.header], invert=True)
        self.draw_lines(self.lines)

class SysPanel(Panel):
    lines = ('{now:%m/%d %H:%M}',
             'CPU {sys.cpu_usage:02.1f}%',
             'MEM {sys.free_mem_mb:0.0f}MB free',
             'UP  {obc.uptime_hr:02d}h {obc.uptime_min:02d}m {obc.uptime_sec:02d}s')

    #lines = ('%(current_time)s',
    #         'CPU %(cpu_usage)02.1f%%',
    #         'MEM %(free_mem)dMB free',
    #         'UP  %(hours)02dh %(minutes)02dm %(seconds)02ds')

    def draw(self):
        self.draw_title('SYS')
        self.draw_mini_stat('{temp.fahrenheit:+0.0f}F')
        self.draw_lines(self.lines)

class GPSPanel(Panel):
    lines = ('QUAL {gps.quality}',
             'LAT  {gps.latitude:+02.5f}',
             'LNG  {gps.longitude:+02.5f}',
             'ALT  {gps.altitude:02.3f}K')

    #lines = ('QUAL %(gps_qual)s',
    #         'LAT  %(gps_lat)+02.5f',
    #         'LNG  %(gps_lng)+02.5f',
    #         'ALT  %(gps_alt)02.3fK')

    def draw(self):
        self.draw_title('GPS')
        self.draw_mini_stat('QUA {gps.quality}')
        self.draw_lines(self.lines)

class DroidPanel(Panel):
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

    lines = ('BAT {droid.battery}% CELL {droid.radio}',
             'PHOTOS {droid.photo_count}',
             'LAT {droid.latitude:+02.5f}',
             'LNG {droid.longitude:+02.5f}')

    #lines = ('BAT %(droid_battery)d%% CELL %(droid_cell)s',
    #         'PHOTOS %(droid_photos)d',
    #         'LAT %(droid_lat)+02.5f',
    #         'LNG %(droid_lng)+02.5f')

    def draw(self):
        for x in range(0, self.bitmap_width):
            for y in range(0, self.bitmap_height):
                line = self.bitmap[y]
                self.screen.draw_pixel(self.origin_x + x, self.origin_y + y,
                                       line & (1 << x))

        self.screen.draw_text(self.origin_x + 1,
                              self.origin_y + self.bitmap_height + 1,
                              'BT:{droid.connected:d}'.format(**self.template_args))

        padding = 2
        line_size = 1
        right_line_x = self.origin_x + self.bitmap_width + padding
        for x in range(0, line_size):
            for y in range(self.origin_y, self.origin_y + self.screen.height):
                self.screen.draw_pixel(right_line_x + x, y, 1)

        self.data_x = right_line_x + line_size + padding
        self.draw_lines(self.lines)

class PanelBuffer(object):
    scroll_interval = 0.01

    def __init__(self, screen, panels):
        self.screen = screen
        self.panels = panels
        for panel in panels:
            panel.in_buffer = True

        self.active = 0

    @property
    def inactive(self):
        return 1 if self.active == 0 else 0

    @property
    def active_panel(self):
        return self.panels[self.active]

    @property
    def inactive_panel(self):
        return self.panels[self.inactive]

    def switch_panel(self, panel):
        try:
            index = self.panels.index(panel)
            self.active = index
        except ValueError, e:
            # new screen
            self.active = self.inactive
            self.panels[self.active].in_buffer = False
            self.panels[self.active] = panel
            panel.in_buffer = True
            self.screen.clear_display()
            panel.do_draw(0, self.active * self.screen.height)
            self.screen.display()

        start_y = self.inactive * self.screen.height
        dest_y = self.active * self.screen.height
        lambda_y = 1 if self.inactive == 0 else -1

        # this takes over the main loop for smooth animation
        for y in range(start_y, dest_y + lambda_y, lambda_y):
            self.screen.set_start_line(y)
            time.sleep(self.scroll_interval)

    def draw(self):
        for i in range(len(self.panels)):
            self.panels[i].do_draw(0, i * self.screen.height)
