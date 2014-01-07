#include "libs.h"
#include "obc.h"
#include "radio.h"
#include "droid.h"

const char kAppName[] = "pepper2"; // the app on your phone
const char kAccessoryName[] = "Arduino Due"; // your Arduino board
const char kCompanyName[] = "Arduino SA";

// Make up anything you want for these
const char kVersion[] = "1.0";
const char kSerialNumber[] = "1";
const char kUrl[] = "http://www.arcaner.com";

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

pepper2::Droid::Droid(pepper2::OBC *obc) :
    mObc(obc),
    mUsb(),
    mAdk(&mUsb, kCompanyName, kAppName, kAccessoryName, kVersion, kUrl,
         kSerialNumber)
{
}

void pepper2::Droid::begin()
{
    cpu_irq_enable();
    delay(200);
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

    Serial.println("[droid] usb task");
    mUsb.Task();

    Serial.println("[droid] adk is ready");
    if (!mAdk.isReady()) {
        return;
    }

    Serial.println("[droid] read..");
    mAdk.read(&bytesRead, sizeof(DroidMessage), (uint8_t *) &msg);
    if (bytesRead == 0) {
        return;
    }

    bytesRead = 0;
    Serial.println("[droid] read again..");
    mAdk.read(&bytesRead, msg.length, data);
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
