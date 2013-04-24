#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <Arduino.h>

#include "nmea_test.h"

int ledPin = 13;
NmeaTest nmeaTest;

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);
  Serial2.begin(9600);
  Serial1.setTimeout(3000);

  pinMode(ledPin, OUTPUT);
}

void p(const char *fmt, ... ){
    char tmp[256]; // resulting string limited to 256 chars
    va_list args;
    va_start (args, fmt );
    vsnprintf(tmp, 256, fmt, args);
    va_end (args);
    Serial.print(tmp);
}

#define COMMANDS_LEN 7
const char *commands[COMMANDS_LEN] = {
  "+++", "ATMY\r", "ATDT\r", "ATVL\r", "ATPL 2\r", "ATPL\r", "ATCN\r"
};

boolean sendAT(const char *command)
{
  char buf[65];

  p("-> %s\n", command);
  Serial1.write(command);
  //Serial1.write("\r");

  unsigned long time = millis();
  byte bytesRead = Serial1.readBytesUntil('\r', buf, 64);
  if (bytesRead == 0) {
     p("%s: error, no response\n", command);
     return false;
  }
  buf[bytesRead] = '\0';

  p("<- %s (%d bytes)\n", buf, bytesRead);
  while (Serial1.available() > 0 && (bytesRead = Serial1.readBytesUntil('\r', buf, 64)) > 0) {
    buf[bytesRead] = '\0';
    p("<- %s (%d bytes)\n", buf, bytesRead);
  }

  time = millis() - time;
  p(":: took %ld ms\n\n", time);
  return true;
}

void handshake()
{/*
  char buf[33];

  byte bytesSent = Serial1.write("+++");
  p("sent %d bytes, waiting for bytes available\n", bytesSent);

  unsigned long time = millis();
  if (!Serial1.find("OK\r")) {
    p("no OK rcvd\n");
    return;
  }

  time = millis() - time;
  p("In AT command mode, took %ld ms\n", time);*/

  for (int i = 0; i < COMMANDS_LEN; i++) {
    if (!sendAT(commands[i])) {
      break;
    }
  }

//  sendAT("ATCN");
}


void terminal()
{
  char buf[33];
  while (Serial.available() > 0) {
    byte bytesRead = Serial.readBytes(buf, 32);
    buf[bytesRead]='\0';

    if (strncasecmp(buf, "HANDSHAKE", strlen("HANDSHAKE")) == 0) {
      handshake();
      return;
    }

    p("-> (%d) %s\n", bytesRead, buf);
    Serial1.write((uint8_t *)buf, bytesRead);
  }

  while (Serial1.available() > 0) {
    byte bytesRead = Serial1.readBytes(buf, 32);
    if (bytesRead == 1) {
      p("<- (1) 0x%x\n", buf[0]);
    }
    else {
      buf[bytesRead]='\0';
      p("<- (%d) %s\n", bytesRead, buf);
    }
  }

  delay(10);
}

void sendHelloWorld()
{
    digitalWrite(ledPin, HIGH);
    Serial1.write("hello from arduino!");
    Serial1.flush();
    delay(500);
    digitalWrite(ledPin, LOW);

    delay(1000);
}

void serialEvent2()
{
    digitalWrite(ledPin, HIGH);
    //Serial.print("GPS >");

    while (Serial2.available()) {
        int b = Serial2.read();
        Serial1.write(b);
        //Serial.print(b, HEX);
    }
    //Serial.println("");
    digitalWrite(ledPin, LOW);
}

bool configured = false;
void loop()
{
    if (!configured) {
        handshake();
        configured = true;
    }

    //nmeaTest.tick();
    //sendHelloWorld();
  //terminal();
  //delay(100000);

  /*const char *cmd1 = "+++";
  Serial1.write((uint8_t *)cmd1, strlen(cmd1));
  Serial.println("-> +++");
  delay(1000);
  dumpSerial1();

  const char *cmd2 = "ATMY\n";
  Serial1.write((uint8_t *)cmd2, strlen(cmd2));
  Serial.println("-> ATMY");
  delay(1000);
  dumpSerial1();

  delay(100000);*/
}
