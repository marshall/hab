#include <stdarg.h>
#include <Arduino.h>

#include "libs.h"
#include "obc.h"
#include "radio.h"

#define RADIO_USART Serial1
#define RADIO_BAUD  9600

#define NMEA_PREFIX    "PPPR"
#define NMEA_TELEMETRY  NMEA_PREFIX "T"
#define NMEA_PHOTO_DATA NMEA_PREFIX "PD"

static const int kTelemetryInterval = 5000;

pepper2::Radio::Radio(pepper2::OBC *obc) :
    mSerial(&RADIO_USART),
    mObc(obc)
{
}

void pepper2::Radio::begin() {
    mSerial->begin(RADIO_BAUD);
}


void pepper2::Radio::sendTelemetry() {
    static const char *kTelemetryFormat = NMEA_TELEMETRY ",%d,%+03.2f,%+03.2f";
    static int nmeaLength;

    mSerial->println(mObc->getLastNmea());
    Serial.println(mObc->getLastNmea());

    buildNmea(NMEA_TELEMETRY, "%d,%+03.2f,%+03.2f",
              (millis() - mObc->getBegin()) / 1000,
              mObc->getTemperature(),
              mObc->getHumidity());

    mSerial->println(mBuffer);
    Serial.println(mBuffer);
}

void pepper2::Radio::buildNmea(const char *type, const char *fmt, ...) {
    static uint8_t i, checksum, length;
    static char checksumStr[4];
    va_list nmeaArgs;
    char *buf = mBuffer;

    i = 0;
    length = 0;

    i = snprintf(buf, RADIO_BUFFER_SIZE, "$%s,", type);
    buf += i;
    length += i;

    va_start(nmeaArgs, fmt);
    i = vsnprintf(buf, RADIO_BUFFER_SIZE - length, fmt, nmeaArgs);
    va_end(nmeaArgs);

    buf += i;
    length += i;

    if (length > RADIO_BUFFER_SIZE - 4) {
        // Line is too long for our buffer!
        return;
    }

    // Skip the prefix $
    for (i = 1, checksum = 0; i < length; i++) {
        checksum ^= (uint8_t) mBuffer[i];
    }

    snprintf(checksumStr, 4, "*%02X", checksum);
    strncat(mBuffer, checksumStr, RADIO_BUFFER_SIZE - 1);
}
