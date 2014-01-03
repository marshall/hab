#ifndef PEPPER2_RADIO_H
#define PEPPER2_RADIO_H

#define RADIO_BUFFER_SIZE 200

namespace pepper2 {

class OBC;
class Radio {
public:
    Radio(OBC *obc);
    void begin();
    void sendTelemetry();

private:
    void buildNmea(const char *type, const char *fmt, ...);

    USARTClass *mSerial;
    OBC *mObc;

    char mBuffer[RADIO_BUFFER_SIZE];
};

}

#endif
