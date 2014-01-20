#include "variant.h"

#include <adk.h>
#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_GPS.h>
#include <Adafruit_SSD1306.h>
#include <dht22.h>
#include <SPI.h>
#include <SD.h>
#include <Usb.h>
#include <Wire.h>

#include "obc.h"

const char kManufacturer[] = "Arduino SA"; // the app on your phone
const char kModel[]        = "Arduino Due"; // your Arduino board
const char kDescription[]  = "pepper2";
const char kVersion[]      = "0.1";
const char kSerial[]       = "1";
const char kUrl[]          = "http://www.arcaner.com";

static USBHost gUsb;
static ADK gAdk(&gUsb, kManufacturer, kModel, kDescription, kVersion, kUrl,
                kSerial);

static pepper2::OBC gObc(&gUsb, &gAdk);

void setup() {
    cpu_irq_enable();
    delay(200);

    gObc.begin();
}

void loop() {
    gObc.loop();
}
