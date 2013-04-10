#include <Arduino.h>

#include "nmea_test.h"

extern "C" {
extern const uint16_t kSentencesLength;
extern const uint16_t kSentencesMaxStringLength;
extern const char *kSentences[] PROGMEM;
}

NmeaTest::NmeaTest() : mSentence(0), mLastSent(0)
{
}

void NmeaTest::tick()
{
    if (millis() - mLastSent < 1000) {
        return;
    }

    char sentence[kSentencesMaxStringLength];
    strcpy_P(sentence, (char*) pgm_read_word(&(kSentences[mSentence])));

    Serial1.write(sentence);
    Serial1.flush();

    mLastSent = millis();
    mSentence++;
    if (mSentence > kSentencesLength - 1) {
        mSentence = 0;
    }
}
