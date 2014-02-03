import logging
import pygame
import sys

from pepper2 import ssd1306

class MockOLED(ssd1306.SSD1306):
    width  = 128
    height = 32
    buffer_height = 64
    scale  = 3
    colors = ((0, 0, 0), (0x66, 255, 255))

    def __init__(self, *args, **kwargs):
        super(MockOLED, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger('mock_oled')

        pygame.init()
        self.window = pygame.display.set_mode((self.width * self.scale,
                                               self.height * self.scale))
        self.window_buffer = pygame.Surface((self.width * self.scale,
                                             self.buffer_height * self.scale))
        self.pixel_rect = pygame.Rect(0, 0, self.scale, self.scale)
        self.top_x = 0
        self.top_y = 0


    def clear_display(self):
        super(MockOLED, self).clear_display()
        self.window_buffer.fill(self.colors[0])

    def display_block(self, bitmap, row, col, col_count, col_offset):
        self.update_display()

    def update_display(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        self.window.blit(self.window_buffer, (0, 0),
                         (0, self.top_y * self.scale,
                          self.width * self.scale, self.height * self.scale))

        pygame.display.update()

    def command(self, *bytes):
        if len(bytes) >= 1:
            cmd = bytes[0]
            if cmd & self.SET_START_LINE:
                self.top_y = cmd & ~self.SET_START_LINE
                self.update_display()

    def draw_pixel(self, x, y, on=True):
        color = self.colors[1 if on else 0]
        self.pixel_rect.x = x * self.scale
        self.pixel_rect.y = y * self.scale
        pygame.draw.rect(self.window_buffer, color, self.pixel_rect)
