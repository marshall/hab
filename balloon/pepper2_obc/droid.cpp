#include "libs.h"
#include "obc.h"
#include "radio.h"
#include "droid.h"

#define LOG_TAG "Droid"
#include "log.h"

const uint8_t kMsgTelemetry = 0;
const uint8_t kMsgPhotoData = 1;

typedef struct __attribute__((packed)) {
    uint8_t battery;
    uint8_t radioLevel;
    uint16_t photoCount;
    double orientationX;
    double orientationY;
    double orientationZ;
    double latitude;
    double longitude;
    double altitude;
} DroidTelemetry;

// Note: is apparently very important that this is initialized at global scope
// don't move it to a member variable :)

//static USBHost gUsb;

pepper2::Droid::Droid(pepper2::OBC *obc, USBHost *usbHost, ADK *adk) :
    mObc(obc),
    mUsbHost(usbHost),
    mAdk(adk)
{
}

void pepper2::Droid::begin()
{
}

uint32_t pepper2::Droid::checksum(uint8_t *data, uint8_t length) {
    uint8_t i = 0;
    uint32_t checksum = 0;
    for (; i < length; i++) {
        checksum ^= (uint8_t) data[i];
    }

    return checksum;
}

void pepper2::Droid::loop()
{
    static DroidMessage msg;
    static uint8_t data[255];
    static uint32_t bytesRead;

    bytesRead = 0;

    mUsbHost->Task();
    if (!mAdk->isReady()) {
        return;
    }

    mAdk->read(&bytesRead, sizeof(DroidMessage), (uint8_t *) &msg);
    if (bytesRead == 0) {
        LOG_DEBUG("read 0 bytes from ADK");
        return;
    }

    LOG_DEBUG("rcvd usb message length %d, type %d, checksum %08x",
              msg.length, msg.type, msg.checksum);

    bytesRead = 0;
    mAdk->read(&bytesRead, msg.length, data);
    if (bytesRead == 0) {
        Serial.println("[droid] error reading msg data");
        return;
    }

    if (checksum(data, msg.length) != msg.checksum) {
        Serial.println("[droid] error confirming msg checksum");
        return;
    }

    switch (msg.type) {
        case kMsgTelemetry:
            handleTelemetry(&msg, data);
            break;
    }
}

void pepper2::Droid::handleTelemetry(DroidMessage *msg, uint8_t *data) {
    mObc->getRadio()->sendNmea(NMEA_DROID_TELEMETRY, "%*s", msg->length, (char *) data);
}
