import pygame
import ssd1306
import sys

class MockOLED(ssd1306.SSD1306):
    width  = 128
    height = 32
    scale  = 3
    colors = ((0, 0, 0), (0x66, 255, 255))

    def __init__(self, *args, **kwargs):
        super(MockOLED, self).__init__(*args, **kwargs)

        pygame.init()
        self.window = pygame.display.set_mode((self.width * self.scale,
                                               self.height * self.scale))
        self.pixel_rect = pygame.Rect(0, 0, self.scale, self.scale)


    def clear_display(self):
        super(MockOLED, self).clear_display()
        pygame.draw.rect(self.window, self.colors[0],
                         (0, 0, self.width * self.scale, self.height * self.scale))

    def display_block(self, bitmap, row, col, col_count, col_offset):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)
        pygame.display.update()

    def draw_pixel(self, x, y, on=True):
        color = self.colors[1 if on else 0]
        self.pixel_rect.x = x * self.scale
        self.pixel_rect.y = y * self.scale
        pygame.draw.rect(self.window, color, self.pixel_rect)
