#include <avr/pgmspace.h>
#include <string.h>

#include <SoftwareSerial.h>
#include <Adafruit_GPS.h>
#include <dht22.h>

#define DHT22_OK         0
#define DHT22_CHKSUM_ERR -1
#define DATA_INTERVAL    2000
#define TEMP_INTERVAL    2000

SoftwareSerial gpsSerial(11, 10);
Adafruit_GPS GPS(&gpsSerial);
dht22 temp(3);

boolean gpsLogging = false;
boolean gpsDateValid = false;

int tempCheck = 0;
char c = 0;
uint32_t timer = millis(), tempTimer = millis();
float internalTemp = 0;
float internalHumidity = 0;
char timestamp[32];

typedef struct {
  uint8_t year, month, day;
  uint8_t hour, minute, second;
  uint16_t ms;
} GPSTime;

GPSTime gpsTime;

void setup() {
  gpsTime.month = 1;
  gpsTime.day = 1;

  Serial.begin(115200);
  gpsSerial.begin(9600);

  delay(500);
  // Initially only request GPRMC until we have a valid date basis
  GPS.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCONLY);
  GPS.sendCommand(PMTK_SET_NMEA_UPDATE_1HZ);
  delay(500);
  
  if (gpsLogging) {
    delay(500);
    GPS.LOCUS_StartLogger();
    delay(1000);
  }
}

float latDegrees() {
  float lat = floor(GPS.latitude / 100.0f);
  lat += (GPS.latitude - (lat * 100)) / 60;
  if (GPS.lat == 'S') {
      lat *= -1;
  }
  return lat;
}

float lngDegrees() {
  float lng = floor(GPS.longitude / 100.0f);
  lng += (GPS.longitude - (lng * 100)) / 60;
  if (GPS.lon == 'W') {
      lng *= -1;
  }
  return lng;
}

void maybeDumpData() {
  gpsTime.hour = GPS.hour;
  gpsTime.minute = GPS.minute;
  gpsTime.second = GPS.seconds;
  gpsTime.ms = GPS.milliseconds;

  // silly heuristic to fix a bug in the time/date updating logic in Adafruit_GPS
  // year should be in 2014..2015, right?
  if (!gpsDateValid && GPS.year >= 14 && GPS.year <= 15) {
      gpsTime.year = GPS.year;
      gpsTime.month = GPS.month;
      gpsTime.day = GPS.day;

      // Turn on GGA sentences
      GPS.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCGGA);
      gpsDateValid = true;
      return;
  }

  if (millis() - timer < DATA_INTERVAL) {
    return;
  }

  snprintf_P(timestamp, 32, PSTR("20%02d-%02d-%02d %02d:%02d:%02d.%03d"),
             gpsTime.year, gpsTime.month, gpsTime.day,
             gpsTime.hour, gpsTime.minute, gpsTime.second, gpsTime.ms);

  Serial.print(F("{\"internal_temp\":"));
  Serial.print(internalTemp, 1);
  Serial.print(F(",\"internal_humidity\":"));
  Serial.print(internalHumidity, 1);
  Serial.print(F(",\"external_temp\":"));
  Serial.print(0, DEC);
  Serial.print(F(",\"external_humidity\":"));
  Serial.print(0, DEC);
  Serial.print(F(",\"gps_latitude\":"));
  Serial.print(latDegrees(), 7);
  Serial.print(F(",\"gps_longitude\":"));
  Serial.print(lngDegrees(), 7);
  Serial.print(F(",\"gps_altitude\":"));
  Serial.print(GPS.altitude, 1);
  Serial.print(F(",\"gps_speed\":"));
  Serial.print(GPS.speed, 1);
  Serial.print(F(",\"gps_quality\":"));
  Serial.print(GPS.fixquality, DEC);
  Serial.print(F(",\"gps_satellites\":"));
  Serial.print(GPS.satellites, DEC);
  Serial.print(F(",\"gps_timestamp\":\""));
  Serial.print(timestamp);
  Serial.println("\"}");
  timer = millis();
}

void loop() {
  if (millis() - tempTimer > TEMP_INTERVAL) {
    do {
      tempCheck = temp.read();
    } while (tempCheck == DHT22_CHKSUM_ERR);

    if (tempCheck == DHT22_OK) {
      internalTemp = temp.celcius();
      internalHumidity = temp.humidity;
    }
    tempTimer = millis();
  }

  while (gpsSerial.available()) {
    c = GPS.read();
    if (GPS.newNMEAreceived()) {
      if (GPS.parse(GPS.lastNMEA())) {
        maybeDumpData();
      }
      return;
    }
  }
}
