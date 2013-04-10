#ifndef NMEA_TEST_H
#define NMEA_TEST_H

class NmeaTest {
private:
    uint16_t mSentence;
    unsigned long mLastSent;

public:
    NmeaTest();
    void tick();
};

#endif
