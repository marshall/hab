#ifndef PEPPER2_DROID_H
#define PEPPER2_DROID_H

namespace pepper2 {

class OBC;

typedef struct __attribute__((packed)) {
    uint8_t length;
    uint8_t type;
    uint32_t checksum;
    uint8_t data[0];
} DroidMessage;

class Droid {
public:
    Droid(OBC *obc, USBHost *usbHost, ADK *adk);
    void begin();
    void loop();

private:
    uint32_t checksum(uint8_t *data, uint8_t length);
    void handleTelemetry(DroidMessage *msg, uint8_t *data);

    OBC *mObc;
    USBHost *mUsbHost;
    ADK *mAdk;
};

}

#endif
