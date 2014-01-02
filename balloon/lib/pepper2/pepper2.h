#ifndef PEPPER2_H
#define PEPPER2_H

namespace pepper2 {

class Stats {
public:
    Stats(Adafruit_SSD1306 &display, dht22 &temp);
    void refresh();
    void setRefreshDelta(uint32_t millis) {
        mRefreshDelta = millis;
    }

private:
    void refreshStats();

    Adafruit_SSD1306 &mDisplay;
    dht22 &mDht22;

    uint32_t mRefreshDelta;
    unsigned long mBegin;
    uint8_t mHours, mMinutes, mSeconds;
    uint8_t mPowerLevel;
    bool mRadioIo, mGpsLock;
    float mTemp, mLat, mLng, mAlt;
};

}

#endif
