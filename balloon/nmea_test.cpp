#include <Arduino.h>

#include "nmea_test.h"
#include "nmea_sentences.h"

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
    Serial1.write("\r\n");
    Serial1.flush();

    mLastSent = millis();
    mSentence++;
    if (mSentence > kSentencesLength - 1) {
        mSentence = 0;
    }
}
