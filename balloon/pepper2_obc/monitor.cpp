#include <string.h>

#include "libs.h"
#include "monitor.h"
#include "obc.h"

#if SSD1306_LCDHEIGHT != 32
#error("Height incorrect, please fix Adafruit_SSD1306.h!");
#endif

// Pins
#define PIN_OLED_MOSI  9
#define PIN_OLED_CLK   10
#define PIN_OLED_DC    11
#define PIN_OLED_CS    12
#define PIN_OLED_RESET 13

#define YN(val) ((val) ? ('Y') : ('N'))

pepper2::Monitor::Monitor(pepper2::OBC *obc) :
    mObc(obc),
    mDisplay(PIN_OLED_MOSI, PIN_OLED_CLK, PIN_OLED_DC, PIN_OLED_RESET,
             PIN_OLED_CS)
{
}

void pepper2::Monitor::begin() {
    mDisplay.begin(SSD1306_SWITCHCAPVCC);
}

void pepper2::Monitor::println(char *message) {
    //Serial.println(message);
    mDisplay.println(message);
}

void pepper2::Monitor::draw() {
    static char lineBuffer[32], gpsBuffer[6];
    static uint8_t hours, minutes, seconds;
    static const char *kMonitorStrings[4] = {
        " PEPPER-2 %02dh%02dm%02ds ",
        "RPL:%1d RIO:%c GPS:%s",
        "TMP:%+02.1fF LAT:%+02.1f",
        "LNG:%+02.1f  ALT:%+02.1fK",
    };

    mDisplay.clearDisplay();
    mDisplay.setTextSize(1);
    mDisplay.setTextColor(BLACK, WHITE);
    mDisplay.setCursor(0,0);

    mObc->getUptime(&hours, &minutes, &seconds);
    snprintf(lineBuffer, 32, kMonitorStrings[0],
             hours, minutes, seconds);
    println(lineBuffer);

    mDisplay.setTextColor(WHITE);

    // width = 21 chars when text size = 1

    if (!mObc->isGpsFixed()) {
        strncpy(gpsBuffer, "NOFIX", 6);
    } else {
        snprintf(gpsBuffer, 6, "%d%%", mObc->getGpsFixQuality());
    }

    snprintf(lineBuffer, 32, kMonitorStrings[1],
             mObc->getPowerLevel(),
             YN(mObc->isRadioLinkActive()),
             gpsBuffer);
    println(lineBuffer);

    snprintf(lineBuffer, 32, kMonitorStrings[2],
             mObc->getTemperature(), mObc->getLatitude());
    println(lineBuffer);

    snprintf(lineBuffer, 32, kMonitorStrings[3],
             mObc->getLongitude(), mObc->getAltitude());
    println(lineBuffer);
    mDisplay.display();
}
