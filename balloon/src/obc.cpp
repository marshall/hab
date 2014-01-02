#include "pepper2.h"

// Pins
#define PIN_DHT22_DTA  2

#define SERIAL_CONSOLE Serial
#define SERIAL_RADIO   Serial1
#define SERIAL_GPS     Serial2

#define DHT22_OK         0
#define DHT22_CHKSUM_ERR -1

pepper2::OBC::OBC() :
    mDht22(PIN_DHT22_DTA),
    mGps(&SERIAL_GPS),
    mRefreshDelta(1000),
    mHours(0),
    mMinutes(0),
    mSeconds(0),
    mPowerLevel(0),
    mRadioLinkActive(false),
    mTemp(0.0f)
{
    mBegin = millis();
    mMonitor = new pepper2::Monitor(this);
}

void pepper2::OBC::getUptime(uint8_t *hours, uint8_t *minutes, uint8_t *seconds) {
    if (hours) {
        *hours = mHours;
    }
    if (minutes) {
        *minutes = mMinutes;
    }
    if (seconds) {
        *seconds = mSeconds;
    }
}

void pepper2::OBC::begin() {
    SERIAL_CONSOLE.begin(115200);

    SERIAL_GPS.begin(9600);
    delay(10);
    mGps.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCGGA);
    mGps.sendCommand(PMTK_SET_NMEA_UPDATE_5HZ);

    mMonitor->begin();
}

void pepper2::OBC::loop() {
    mGps.read();
    if (mGps.newNMEAreceived()) {
        char *lastNMEA = mGps.lastNMEA();
        mGps.parse(lastNMEA);
    }

    if (millis() - mBegin < mRefreshDelta) {
        return;
    }

    updateData();
    mMonitor->draw();
}

void pepper2::OBC::updateData() {
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

