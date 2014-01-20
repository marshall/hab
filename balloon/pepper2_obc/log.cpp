#include <stdarg.h>
#include <string.h>

#include "libs.h"
#include "log.h"
#include "obc.h"

#define PIN_SDCS 4

static pepper2::Logger *gLogger = NULL;
static const char kLogFile[] = "pepper2.log";

pepper2::Logger::Logger(OBC *obc) :
    mObc(obc),
    mConsoleLevel(LOG_LEVEL_DEBUG),
    mFileLevel(LOG_LEVEL_DEBUG),
    mFileEnabled(false)
{
}


void pepper2::Logger::begin() {
    pinMode(PIN_SDCS, OUTPUT);
    mFileEnabled = SD.begin(PIN_SDCS);
}

void pepper2::Logger::vlog(uint8_t level, const char *fmt, va_list ap) {
    static const char kTimestampFormat[] = "[%4d-%02d-%02d %02d:%02d:%02d.%03d] ";

    Adafruit_GPS &gps = mObc->getGps();
    snprintf(mTimestamp, LOG_BUFFER_SIZE, kTimestampFormat,
             2000 + gps.year, gps.month, gps.day,
            gps.hour, gps.minute, gps.seconds, gps.milliseconds);

    vsnprintf(mBuffer, LOG_BUFFER_SIZE, fmt, ap);

    if (level <= mConsoleLevel) {
        SERIAL_CONSOLE.print(mTimestamp);
        SERIAL_CONSOLE.println(mBuffer);
    }

    if (mFileEnabled && level <= mFileLevel) {
        File f = SD.open(kLogFile);
        f.print(mTimestamp);
        f.println(mBuffer);
        f.close();
    }
}

void pepper2::logInit(pepper2::OBC *obc) {
    if (gLogger == NULL) {
        gLogger = new pepper2::Logger(obc);
        gLogger->begin();
    }
}

void pepper2::log(uint8_t level, const char *fmt, ...) {
    if (level > gLogger->getConsoleLevel() &&
        level > gLogger->getFileLevel()) {
        return;
    }

    va_list ap;
    va_start(ap, fmt);
    gLogger->vlog(level, fmt, ap);
    va_end(ap);
}

void pepper2::setFileLogLevel(int level) {
    gLogger->setFileLevel(level);
}

void pepper2::setConsoleLogLevel(int level) {
    gLogger->setConsoleLevel(level);
}
