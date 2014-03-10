import collections
import logging

import gevent
from pynmea import nmea
import serial

import hab_utils
import proto
import worker

class GPS(worker.FileReadLineWorker):
    fix_count = 5

    init_sentences = (
        '$PMTK220,1000*1F', # Update @ 1Hz
        '$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28') # Output RMC and GGA only

    def __init__(self, port='/dev/ttyO1', baud=9600, uart='UART1', handler=None):
        self.latitude = self.longitude = self.altitude = self.quality = 0
        self.satellites = self.speed = 0
        self.fixes = collections.deque([], self.fix_count)
        self.handler = handler

        if uart:
            import Adafruit_BBIO.UART
            Adafruit_BBIO.UART.setup(uart)

        super(GPS, self).__init__(file=serial.Serial(port=port,
                                                     baudrate=baud,
                                                     timeout=0.25))

    def started(self):
        for sentence in self.init_sentences:
            self.write(sentence + '\r\n')

    def work(self):
        sentence = nmea.parse_sentence(self.line)
        if not isinstance(sentence, nmea.GPGGA) or not hasattr(sentence, 'latitude'):
            return

        # self.log.info(self.line)
        try:
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
            if self.handler:
                self.handler(self)

            self.fixes.append((self.latitude, self.longitude, self.altitude, self.quality))
        except ValueError as e:
            pass

    def update_timestamp(self, timestamp):
        if len(timestamp) < 5:
            return

        ts_hr, ts_min, ts_sec = int(timestamp[0:2]), int(timestamp[2:4]), float(timestamp[4:])
