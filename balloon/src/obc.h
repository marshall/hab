#ifndef PEPPER2_OBC_H
#define PEPPER2_OBC_H

#define SERIAL_CONSOLE Serial
#define SERIAL_RADIO   Serial1
#define SERIAL_GPS     Serial2

#define OBC_LAST_NMEA_SIZE 200

namespace pepper2 {

class Droid;
class Monitor;
class Radio;

class OBC {
public:
    OBC();
    void begin();
    float getAltitude();
    float getLatitude();
    float getLongitude();
    void getUptime(uint8_t *hours, uint8_t *minutes, uint8_t *seconds);
    void loop();

    uint32_t getBegin() { return mBegin; }
    uint8_t getGpsFixQuality() { return mGps.fixquality; }
    Adafruit_GPS& getGps() { return mGps; }
    float getHumidity() { return mHumidity; }
    char *getLastNmea() { return mLastNmea; }
    uint8_t getPowerLevel() { return mPowerLevel; }
    Radio* getRadio() { return mRadio; }
    float getTemperature() { return mTemp; }
    bool isGpsFixed() { return mGps.fix; }
    bool isRadioLinkActive () { return mRadioLinkActive; }

private:
    void updateData();
    void updateGps();
    void updateTemp();

    Monitor *mMonitor;
    Radio *mRadio;
    Droid *mDroid;
    dht22 mDht22;
    Adafruit_GPS mGps;

    uint32_t mBegin, mLastMonitor, mLastTelemetry;
    uint8_t mHours, mMinutes, mSeconds;
    uint8_t mPowerLevel;
    char mLastNmea[OBC_LAST_NMEA_SIZE];
    bool mRadioLinkActive;
    float mTemp, mHumidity;
};

}

#endif
