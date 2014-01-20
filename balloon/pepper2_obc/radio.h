#ifndef PEPPER2_RADIO_H
#define PEPPER2_RADIO_H

#define RADIO_BUFFER_SIZE 200

#define NMEA_PREFIX          "PPR2"
#define NMEA_TELEMETRY       NMEA_PREFIX "T"
#define NMEA_DROID_TELEMETRY NMEA_PREFIX "DT"
#define NMEA_PHOTO_DATA      NMEA_PREFIX "PD"

namespace pepper2 {

class OBC;
class Radio {
public:
    Radio(OBC *obc);
    void begin();
    void sendTelemetry();
    void sendNmea(const char *type, const char *fmt, ...);

private:
    USARTClass *mSerial;
    OBC *mObc;

    char mBuffer[RADIO_BUFFER_SIZE];
};

}

#endif
