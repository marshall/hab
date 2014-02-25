/*
  DHT22 reader for Beaglebone
  
  Inspired by adafruit code : 
    https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/tree/master/Adafruit_DHT_Driver
  Library used for GPIO access : 
    https://github.com/majestik666/Beagle_GPIO
  
*/
#include "Beagle_GPIO.hh"
#include <time.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <iostream>

#define MAXTIMINGS 100

#define DHT11 1
#define DHT22 2
#define SENSOR_NAME(sensor) ((sensor == DHT11)?"DHT11":"DHT22")

#define BIG_NUMBER 1000

#define ABS(a)  (((a)<0)?-(a):(a))

timespec diff(timespec start, timespec end);

static Beagle_GPIO gpio;
static struct timespec startTime;
static clockid_t clk_id = CLOCK_REALTIME ;
static int debug = false;
static int max_timeout = 10;

void check_timeout();
int main(int argc, char* argv[])
{
  int counter = 0;
  int laststate = 1;
  int j = 0;
  int d = 0;
  unsigned short pin = Beagle_GPIO::P8_17; // ving: GPIO conf
  int bits[250], state[250], data[100];
  struct timespec timestamp[250];
  int bitidx = 0;
  float f, h;
  int sensor = DHT22;
  int c, index;
  char* cvalue;

  // argument parsing
  opterr = 0;

  while ((c = getopt (argc, argv, "hdp:s:t:")) != -1)
    switch (c)
    {
      case 'd':
        debug = true;
        break;
      case 's':
        if (strcmp(optarg, "dht11") == 0) { sensor = DHT11; }
        break;
      case 'p':
        pin = atoi(optarg);
        break;
      case 't':
        max_timeout = atoi(optarg);
        break;
      default:
        fprintf(stderr, "Usage:\n\t%s [-d] [-s sensorname] [-p pin_number] [-t max_timeout]\n\t-d: debug\n\t-s: specify sensor, default dht22", argv[0]);
    }

  clock_gettime(clk_id, &startTime);
  while (true) {
    bitidx = 0;
    counter = 0;
    laststate = 1;
    j = 0;
    clk_id = CLOCK_REALTIME ;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    //std::cerr << "Configuring Pin P8_4 as Output\n";
    gpio.configurePin( pin, Beagle_GPIO::kOUTPUT );
    gpio.enablePinInterrupts( pin, false );

    // Initialize DHT22 sensor
    gpio.writePin( pin, 0 );
    usleep(20000);  // 500 ms
    gpio.writePin( pin, 1 );
    usleep(40);

    gpio.configurePin( pin, Beagle_GPIO::kINPUT );
    gpio.enablePinInterrupts( pin, false );

    if (debug) { std::cerr << "-"; }
    while (gpio.readPin(pin) == 0) {
      check_timeout();
      usleep(1);
    }
    if (debug) { std::cerr << "-"; }
    while (gpio.readPin(pin) == 0) {
      check_timeout();
      usleep(1);
    }
    // read data!
    if (debug) { std::cerr << ">"; }
    for (int i=0; i< MAXTIMINGS; i++) {
      counter = 0;
      while ( gpio.readPin(pin) == laststate) {
        counter++;
        //usleep(1);
        if (counter == 400)
          break;
        check_timeout();
      }
      //laststate = gpio.readPin(pin);
      laststate = gpio.readPin(pin);
      if (counter == 400) break;
      state[bitidx] = laststate;
      clock_gettime(clk_id, &timestamp[bitidx]);
      bits[bitidx++] = counter;
      check_timeout();
    }

    // analyse data and 
    j = 0;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;
    //std::cerr << "bitidx=" << bitidx << "\n";
    for (int i=0; i<bitidx; i++) {
      if ((i > 1) && (i%2 == 0)) {
        // shove each bit into the storage bytes
        if (debug) {
          if (j%8 == 0) {
            std::cerr << "\n" << j/8;
          }
          if (debug) {
            std::cerr << " " << (diff(timestamp[i-1], timestamp[i]).tv_nsec/1000);
          }
        }
        d = diff(timestamp[i-1], timestamp[i]).tv_nsec/1000;
        if (d < 20 || d > 80 ){
          bitidx = -1;
          break;
        }
        data[j/8] <<= 1;
        if (d > 40) { data[j/8] |= 1; }
        j++;
      }
      check_timeout();
    }

    if (debug) {
      if (bitidx > 0) {
        std::cerr << "\nbitidx=" << bitidx << "\n";
      } else {
        std::cerr << ".";
      }
    }

    // Compute the checksum
    int checksum = (data[0] + data [1] + data [2] + data [3]) & 0xFF;
    if (debug) {
      if (checksum != 0) {
        for (int i=0; i < 5; i++) {
          fprintf(stderr, "data[%d]=%0d ", i, data[i]);
        }
        std::cerr << "Checksum= " << checksum << "\n";
      }
    }
    if (checksum != data[4] || (checksum == 0)) {
      continue;
    }

    // Compute the Temp & Hum from data (for RHT3 / DHT22)
    if (DHT22 == sensor) {
      h = data[0] * 256 + data[1];
      h /= 10;

      f = (data[2] & 0x7F)* 256 + data[3];
      f /= 10.0;
      if (data[2] & 0x80)  f *= -1;
    } else if (DHT11 == sensor) {
      h = data[0];
      f = data[2];
      if (data[2] & 0x80)  f *= -1;
    }

    // Print to console
    if (bitidx > 40 && h >= 0 && h <= 100) { // check humidity range
        //found
      if(debug) {
        std::cerr << "Temp = " << h << "°C, Hum = " << f << "% bitidx=" << bitidx << "\n";
      }
      printf("{\"status\": \"ok\", \"id\":\"%s\", \"result\":{\"temperature\": %.2f, \"humidity\": %.2f}}", SENSOR_NAME(sensor), f, h);
      exit(0);
    } else {
      usleep(200000); // sleep 200ms
    }
    check_timeout();
  }
}

void check_timeout() {
  struct timespec now;
  clock_gettime(clk_id, &now);
  if ( (now.tv_sec - startTime.tv_sec) > max_timeout) {
    std::cout << "{\"status\": \"error\", \"message\":  \"timeout\"}";
    exit(0);
  }
}

/* Compute diff for timespec (from clock_gettime)*/
timespec diff(timespec start, timespec end)
{
  timespec temp;
  if ((end.tv_nsec-start.tv_nsec)<0) {
    temp.tv_sec = end.tv_sec-start.tv_sec-1;
    temp.tv_nsec = 1000000000+end.tv_nsec-start.tv_nsec;
  } else {
    temp.tv_sec = end.tv_sec-start.tv_sec;
    temp.tv_nsec = end.tv_nsec-start.tv_nsec;
  }
  return temp;
}
