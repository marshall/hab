#include "libs.h"
#include "monitor.h"
#include "obc.h"
#include "radio.h"
#include "droid.h"

#define LOG_TAG "OBC"
#include "log.h"

// Pins
#define PIN_DHT22_DTA  2

#define DHT22_OK         0
#define DHT22_CHKSUM_ERR -1

static const int kMonitorInterval = 1000;
static const int kTelemetryInterval = 5000;

pepper2::OBC::OBC() :
    mDht22(PIN_DHT22_DTA),
    mGps(&SERIAL_GPS),
    mLastMonitor(0),
    mLastTelemetry(0),
    mHours(0),
    mMinutes(0),
    mSeconds(0),
    mPowerLevel(0),
    mRadioLinkActive(false),
    mTemp(0.0f),
    mHumidity(0.0f)
{
    mBegin = millis();
    mMonitor = new pepper2::Monitor(this);
    mRadio = new pepper2::Radio(this);
    mDroid = new pepper2::Droid(this);
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
    logInit(this);

    LOG_DEBUG("GPS begin");
    SERIAL_GPS.begin(9600);
    delay(10);

    LOG_DEBUG("GPS: SET_NMEA_OUTPUT_RMCGGA");
    mGps.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCGGA);
    LOG_DEBUG("GPS: SET_NMEA_UPDATE_1HZ");
    mGps.sendCommand(PMTK_SET_NMEA_UPDATE_1HZ);

    mRadio->begin();
    mMonitor->begin();
    mDroid->begin();

    LOG_INFO("booted in %d ms", millis() - mBegin);
}

void pepper2::OBC::loop() {
    updateData();

    if (millis() - mLastTelemetry >= kTelemetryInterval) {
        mRadio->sendTelemetry();
        mLastTelemetry = millis();
    }

    if (millis() - mLastMonitor >= kMonitorInterval) {
        mMonitor->draw();
        mLastMonitor = millis();
    }

    mDroid->loop();
}

float pepper2::OBC::getLatitude() {
    // Latitude in decimal
    float lat = floor(mGps.latitude / 100.0f);
    lat += (mGps.latitude - (lat * 100)) / 60;
    if (mGps.lat == 'S') {
        lat *= -1;
    }

    return lat;
}

float pepper2::OBC::getLongitude() {
    float lng = floor(mGps.longitude / 100.0f);
    lng += (mGps.longitude - (lng * 100)) / 60;
    if (mGps.lon == 'W') {
        lng *= -1;
    }

    return lng;
}

float pepper2::OBC::getAltitude() {
    // Altitude in KM
    return mGps.altitude / 1000.0f;
}

void pepper2::OBC::updateData() {
    static unsigned long uptime, hourSecs;
    uptime = millis() - mBegin;
    mHours = uptime / (60 * 60 * 1000);
    hourSecs = mHours * 60 * 60 * 1000;
    mMinutes = (uptime - hourSecs) / (60 * 1000);
    mSeconds = (uptime - hourSecs - (mMinutes * 60 * 1000)) / 1000;

    updateTemp();
    updateGps();
}

void pepper2::OBC::updateTemp() {
    static int tempCheck;
    do {
        tempCheck = mDht22.read();
        delay(1);
    } while (tempCheck == DHT22_CHKSUM_ERR); // checksum errors can just be tried again

    if (tempCheck == DHT22_OK) {
        mTemp = (float) mDht22.fahrenheit();
        mHumidity = (float) mDht22.humidity;
    }
}

void pepper2::OBC::updateGps() {
    while (SERIAL_GPS.available()) {
        mGps.read();
        if (!mGps.newNMEAreceived()) {
            continue;
        }
    }

    strncpy(mLastNmea, mGps.lastNMEA(), OBC_LAST_NMEA_SIZE - 1);
    mGps.parse(mLastNmea);
}

static pepper2::OBC gObc;

void setup() {
    gObc.begin();
}

void loop() {
    gObc.loop();
}
