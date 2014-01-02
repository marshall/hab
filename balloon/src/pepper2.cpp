#include <Arduino.h>
#include <Wire.h>

#include "pepper2.h"

pepper2::OBC obc;

#if SSD1306_LCDHEIGHT != 32
#error("Height incorrect, please fix Adafruit_SSD1306.h!");
#endif

void setup() {
    obc.begin();
}

void loop() {
    obc.loop();
}
