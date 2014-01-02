#include <stdlib.h>

#include "Arduino.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <dht22.h>
#include <Wire.h>

#include "pepper2.h"

#define DHT22_DTA  2
#define OLED_MOSI  9
#define OLED_CLK   10
#define OLED_DC    11
#define OLED_CS    12
#define OLED_RESET 13

Adafruit_SSD1306 display(OLED_MOSI, OLED_CLK, OLED_DC, OLED_RESET, OLED_CS);
dht22 temp(DHT22_DTA);

pepper2::Stats stats(display, temp);

#if SSD1306_LCDHEIGHT != 32
#error("Height incorrect, please fix Adafruit_SSD1306.h!");
#endif

void setup() {
    Serial.begin(115200);
    display.begin(SSD1306_SWITCHCAPVCC);
}

void loop() {
    stats.refresh();
}
