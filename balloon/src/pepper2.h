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
    bool isGpsLocked() { return mGpsLock; }
    float getTemperature() { return mTemp; }
    float getLatitude() { return mLat; }
    float getLongitude() { return mLng; }
    float getAltitude() { return mAlt; }

private:
    void updateData();

    Monitor *mMonitor;
    dht22 mDht22;

    uint32_t mRefreshDelta;
    uint32_t mBegin;
    uint8_t mHours, mMinutes, mSeconds;
    uint8_t mPowerLevel;
    bool mRadioLinkActive, mGpsLock;
    float mTemp, mLat, mLng, mAlt;
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
