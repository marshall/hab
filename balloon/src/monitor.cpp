#include <string.h>
#include "pepper2.h"

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

void pepper2::Monitor::draw() {
    static char lineBuffer[32];
    static uint8_t hours, minutes, seconds;
    static const char *kMonitorStrings[4] = {
        " PEPPER-2 %02dh%02dm%02ds ",
        "RPL:%1d  RIO:%c  GPS:%c",
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
    mDisplay.println(lineBuffer);

    mDisplay.setTextColor(WHITE);

    // width = 21 chars when text size = 1
    snprintf(lineBuffer, 32, kMonitorStrings[1],
             mObc->getPowerLevel(),
             YN(mObc->isRadioLinkActive()),
             YN(mObc->isGpsLocked()));
    mDisplay.println(lineBuffer);

    snprintf(lineBuffer, 32, kMonitorStrings[2],
             mObc->getTemperature(), mObc->getLatitude());
    mDisplay.println(lineBuffer);

    snprintf(lineBuffer, 32, kMonitorStrings[3],
             mObc->getLongitude(), mObc->getAltitude());
    mDisplay.println(lineBuffer);
    mDisplay.display();
}
