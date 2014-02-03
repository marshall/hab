import collections
import logging

import Adafruit_BBIO.UART
import gevent
from pynmea import nmea
import serial

import hab_utils

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
        self.gpgga = self.gprmc = None
        self.fixes = collections.deque([], self.fix_count)

        self.log.debug('setting up')
        Adafruit_BBIO.UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=0.25)
        gevent.sleep(0.01) # 10 ms
        for sentence in self.init_sentences:
            self.serial.write(sentence + '\r\n')

    def update(self):
        line = self.serial.readline()
        if not line:
            return

        sentence = nmea.parse_sentence(line)

        if isinstance(sentence, nmea.GPGGA):
            self.gpgga = line.strip()
        elif isinstance(sentence, nmea.GPRMC):
            self.gprmc = line.strip()

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

        self.quality = int(sentence.gps_qual)
        self.fixes.append((self.latitude, self.longitude, self.altitude, self.quality))

    def update_timestamp(self, timestamp):
        if len(timestamp) < 5:
            return

        ts_hr, ts_min, ts_sec = int(timestamp[0:2]), int(timestamp[2:4]), float(timestamp[4:])
        self.log.debug('timestamp = %d:%d:%0.2f', ts_hr, ts_min, ts_sec)

    @property
    def telemetry(self):
        t = []
        if self.gprmc:
            t.append(self.gprmc)
        if self.gpgga:
            t.append(self.gpgga)
        return t


