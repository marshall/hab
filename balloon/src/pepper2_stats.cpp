#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <dht22.h>

#include "pepper2.h"

#define YN(val) ((val) ? ('Y') : ('N'))

#define DHT22_OK         0
#define DHT22_CHKSUM_ERR -1

pepper2::Stats::Stats(Adafruit_SSD1306 &display, dht22 &temp) :
    mDisplay(display),
    mDht22(temp),
    mPowerLevel(0),
    mRadioIo(false),
    mGpsLock(false),
    mTemp(0.0f),
    mLat(0.0f),
    mLng(0.0f),
    mAlt(0.0f)
{
    mBegin = millis();
}

void pepper2::Stats::refreshStats() {
    static unsigned long uptime, hourSecs;
    uptime = millis() - mBegin;
    mHours = uptime / (60 * 60 * 1000);
    hourSecs = mHours * 60 * 60 * 1000;
    mMinutes = (uptime - hourSecs) / (60 * 1000);
    mSeconds = (uptime - hourSecs - (mMinutes * 60 * 1000)) / 1000;

    static int tempCheck;
    do {
        tempCheck = mDht22.read();
        delay(1);
    } while (tempCheck == DHT22_CHKSUM_ERR); // checksum errors can just be tried again

    if (tempCheck == DHT22_OK) {
        mTemp = (float) mDht22.fahrenheit();
    }
}

void pepper2::Stats::refresh() {
    static char lineBuffer[32];
    if (millis() - mBegin < mRefreshDelta) {
        return;
    }

    refreshStats();

    mDisplay.clearDisplay();
    mDisplay.setTextSize(1);
    mDisplay.setTextColor(BLACK, WHITE);
    mDisplay.setCursor(0,0);

    snprintf(lineBuffer, 32, " PEPPER-2 %02dh%02dm%02ds ",
             mHours, mMinutes, mSeconds);
    mDisplay.println(lineBuffer);

    mDisplay.setTextColor(WHITE);

    // width = 21 chars when text size = 1
    snprintf(lineBuffer, 32, "RPL:%1d  RIO:%c  GPS:%c",
             mPowerLevel, YN(mRadioIo), YN(mGpsLock));
    mDisplay.println(lineBuffer);

    snprintf(lineBuffer, 32, "TMP:%+02.1fF LAT:%+02.1f", mTemp, mLat);
    mDisplay.println(lineBuffer);

    snprintf(lineBuffer, 32, "LNG:%+02.1f ALT:%+02.1fK", mLng, mAlt);
    mDisplay.println(lineBuffer);

    mDisplay.display();
}
