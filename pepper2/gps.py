import collections
import logging

import Adafruit_BBIO.UART
import gevent
from pynmea import nmea
import serial

import hab_utils
import proto

class GPS(object):
    uart = 'UART1'
    port = '/dev/ttyO1'
    baud = 9600
    fix_count = 5

    init_sentences = (
        '$PMTK220,1000*1F', # Update @ 1Hz
        '$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28') # Output RMC and GGA only

    def __init__(self):
        self.log = logging.getLogger('gps')
        self.latitude = self.longitude = self.altitude = self.quality = 0
        self.satellites = self.speed = 0
        self.fixes = collections.deque([], self.fix_count)

        self.log.debug('setting up')
        Adafruit_BBIO.UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=0.25)
        gevent.sleep(0.01) # 10 ms
        for sentence in self.init_sentences:
            self.serial.write(sentence + '\r\n')

        gevent.spawn(self.gps_loop)

    def update(self, line):
        sentence = nmea.parse_sentence(line)
        if not isinstance(sentence, nmea.GPGGA):
            return

        self.update_timestamp(sentence.timestamp)

        if len(sentence.latitude) > 0:
            self.latitude = hab_utils.lat2float(float(sentence.latitude),
                                                sentence.lat_direction)
        if len(sentence.longitude) > 0:
            self.longitude = hab_utils.lng2float(float(sentence.longitude),
                                                 sentence.lon_direction)

        if len(sentence.antenna_altitude) > 0:
            self.altitude = float(sentence.antenna_altitude) / 1000.0

        self.satellites = int(sentence.num_sats)
        self.quality = int(sentence.gps_qual)
        self.fixes.append((self.latitude, self.longitude, self.altitude, self.quality))

    def update_timestamp(self, timestamp):
        if len(timestamp) < 5:
            return

        ts_hr, ts_min, ts_sec = int(timestamp[0:2]), int(timestamp[2:4]), float(timestamp[4:])
        self.log.debug('timestamp = %d:%d:%0.2f', ts_hr, ts_min, ts_sec)

    def gps_loop(self):
        self.running = True
        while self.running:
            gevent.socket.wait_read(self.serial.fileno())
            line = self.serial.readline()
            if not line:
                continue
            self.update(line)
