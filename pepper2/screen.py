import datetime
import logging
import time

import gevent

import ssd1306
import worker

class Screen(worker.Worker):
    bus               = 1
    device            = 0
    reset_pin         = 'P9_13'
    dc_pin            = 'P9_15'

    worker_interval = 1.0
    switch_interval = 5.0

    def __init__(self, obc, auto_switch=True):
        super(Screen, self).__init__()
        self.obc = obc
        self.panel = 0
        self.oled = ssd1306.SSD1306(bus=self.bus, device=self.device,
                                    reset_pin=self.reset_pin, dc_pin=self.dc_pin)

        self.panels = [SysPanel(self), GPSPanel(self), DroidPanel(self)]
        self.panel_buffer = PanelBuffer(self, self.panels[0:2])
        self.height = self.oled.rows
        self.font_width = self.oled.font.cols
        self.font_height = self.oled.font.rows
        self.auto_switch = auto_switch
        self.switcher = None

    def started(self):
        self.oled.begin()
        if self.auto_switch:
            self.switcher = worker.spawn(self.next_active_panel, interval=self.switch_interval)

    def stopped(self):
        if self.switcher:
            self.switcher.stop()

    def yn(self, val):
        return 'Y' if val else 'N'

    def clear_display(self):
        self.oled.clear_display()

    def display(self):
        self.oled.display()

    def draw_pixel(self, x, y, value):
        self.oled.draw_pixel(x, y, value)

    def draw_line(self, x1, y1, x2, y2, color=True):
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        dx = x2 - x1
        dy = y2 - y1
        if left == right:
            for y in xrange(top, bottom + 1):
                self.oled.draw_pixel(left, y, color)
        elif top == bottom:
            for x in xrange(left, right + 1):
                self.oled.draw_pixel(x, top, color)
        else:
            for x in xrange(left, right + 1):
                y = top + dy * (x - left) / dx
                self.oled.draw_pixel(x, y, color)

    def draw_rect(self, x, y, width, height, fill=False):
        if fill:
            for _y in xrange(y, y + height):
                for _x in xrange(x, x + width):
                    self.oled.draw_pixel(_x, _y, 1)

        else:
            left, top = x, y
            right, bottom = x + width - 1, y + height - 1
            self.draw_line(left, top, right, top)
            self.draw_line(right, top, right, bottom)
            self.draw_line(right, bottom, left, bottom)
            self.draw_line(left, bottom, left, top)

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
        return dict(obc=self.obc,
                    sys=self.obc.sys,
                    gps=self.obc.gps,
                    droid=self.obc.droid,
                    int_temp=self.obc.dht22.fahrenheit(),
                    int_humidity=self.obc.dht22.humidity,
                    ext_temp=self.obc.ds18b20.fahrenheit(),
                    now=datetime.datetime.now())

    def work(self):
        template_args = self.build_template_args()

        self.oled.clear_display()
        for panel in self.panels:
            panel.template_args = template_args

        self.panel_buffer.draw()
        self.oled.display()

class Panel(object):
    def __init__(self, screen):
        self.log = logging.getLogger('panel')
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

class SysPanel(Panel):
    lines = ('{int_temp:+0.0f}F {int_humidity:0.0f}%',
             'CPU {sys.cpu_usage:02.1f}%',
             'MEM {sys.free_mem_mb:0.0f}MB free',
             'UP  {obc.uptime.hours:02d}h {obc.uptime.minutes:02d}m {obc.uptime.seconds:02d}s')

    def draw(self):
        self.draw_title('SYS')
        self.draw_mini_stat('{now:%H:%M}')
        self.draw_lines(self.lines)

class GPSPanel(Panel):
    lines = ('LAT  {gps.latitude:+02.5f}',
             'LNG  {gps.longitude:+02.5f}',
             'ALT  {gps.altitude:02.3f}K',
             'SPD  {gps.speed:0.1f}')

    def draw(self):
        self.draw_title('GPS')
        self.draw_mini_stat('C{gps.satellites} Q{gps.quality}')
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

    lines = ('BAT {droid.battery}%',
             'STA {droid.accel_state} PH {droid.photo_count}',
             'LAT {droid.latitude:+02.5f}',
             'LNG {droid.longitude:+02.5f}')

    def draw_bars(self):
        active_bars = 0
        if 'droid' in self.template_args:
            radio_bars = self.template_args['droid'].radio_bars
            active_bars = int(self.template_args['droid'].radio_bars/25.0)

        self.screen.draw_text(self.origin_x + 80, self.origin_y, 'CELL')

        right_edge = 128
        bar_width = 5
        bar_base_height = 4
        for b in xrange(0, 4):
            bar_x = self.origin_x + right_edge - ((bar_width + 1) * (4 - b))
            bar_y = self.origin_y + (3 - b)
            fill = b <= active_bars
            self.screen.draw_rect(bar_x, bar_y, bar_width, bar_base_height + b, fill=fill)


    def draw(self):
        for x in xrange(0, self.bitmap_width):
            for y in xrange(0, self.bitmap_height):
                line = self.bitmap[y]
                self.screen.draw_pixel(self.origin_x + x, self.origin_y + y,
                                       line & (1 << x))

        self.draw_bars()

        connected = 0
        if 'droid' in self.template_args:
            connected = self.template_args['droid'].connected

        self.screen.draw_text(self.origin_x + 1,
                              self.origin_y + self.bitmap_height + 1,
                              'BT:{connected:d}'.format(connected=connected))

        padding = 2
        line_size = 1
        right_line_x = self.origin_x + self.bitmap_width + padding
        for x in range(0, line_size):
            for y in range(self.origin_y, self.origin_y + self.screen.height):
                self.screen.draw_pixel(right_line_x + x, y, 1)

        self.data_x = right_line_x + line_size + padding
        self.draw_lines(self.lines)

class PanelBuffer(object):
    scroll_interval = 0.005

    def __init__(self, screen, panels):
        self.screen = screen
        self.panels = panels
        self.panel = None
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
        self.panel = panel
        self.screen.clear_display()
        self.draw()
        self.screen.display()
        '''try:
            index = self.panels.index(panel)
            self.active = index
        except ValueError, e:
            # new screen
            self.active = self.inactive
            self.panels[self.active].in_buffer = False
            self.panels[self.active] = panel
            panel.in_buffer = True
            self.screen.clear_display()
            self.draw()
            self.screen.display()

        start_y = self.inactive * self.screen.height
        dest_y = self.active * self.screen.height
        lambda_y = 1 if self.inactive == 0 else -1

        # this takes over the main loop for smooth animation
        for y in range(start_y, dest_y + lambda_y, lambda_y):
            self.screen.set_start_line(y)
            time.sleep(self.scroll_interval)'''

    def draw(self):
        if self.panel:
            self.panel.do_draw(0, 0)
        '''for i in range(len(self.panels)):
            self.panels[i].do_draw(0, i * self.screen.height)'''
