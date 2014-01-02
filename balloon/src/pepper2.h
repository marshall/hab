#ifndef PEPPER2_H
#define PEPPER2_H

#include "libs.h"

namespace pepper2 {

class Monitor;
class OBC {
public:
    OBC();
    void begin();
    void getUptime(uint8_t *hours, uint8_t *minutes, uint8_t *seconds);
    void loop();

    uint32_t getRefreshDelta() { return mRefreshDelta; }
    uint32_t getBegin() { return mBegin; }
    uint8_t getPowerLevel() { return mPowerLevel; }
    bool isRadioLinkActive () { return mRadioLinkActive; }
    bool isGpsFixed() { return mGps.fix; }
    float getTemperature() { return mTemp; }
    float getLatitude() { return mGps.latitude; }
    float getLongitude() { return mGps.longitude; }
    float getAltitude() { return mGps.altitude; }
    uint8_t getGpsFixQuality() { return mGps.fixquality; }

private:
    void updateData();

    Monitor *mMonitor;
    dht22 mDht22;
    Adafruit_GPS mGps;

    uint32_t mRefreshDelta;
    uint32_t mBegin;
    uint8_t mHours, mMinutes, mSeconds;
    uint8_t mPowerLevel;
    bool mRadioLinkActive;
    float mTemp;
};

class Monitor {
public:
    Monitor(OBC *obc);
    void begin();
    void draw();

private:
    OBC *mObc;
    Adafruit_SSD1306 mDisplay;
};

}

#endif
