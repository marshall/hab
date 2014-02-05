import logging
import json

import gevent
import serial

from Adafruit_BBIO import UART

class Sensors(gevent.Greenlet):
    uart = 'UART1'
    port = '/dev/ttyO1'
    baud = 115200

    def __init__(self):
        super(Sensors, self).__init__()
        self.log = logging.getLogger('sensors')
        self.internal_temp = self.internal_humidity = 0
        self.external_temp = self.external_humidity = 0
        self.gps_latitude = self.gps_longitude = 0
        self.gps_altitude = self.gps_quality = 0
        self.gps_speed = self.gps_satellites = 0
        self.gps_timestamp = ''

        self.running = False
        UART.setup(self.uart)

        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=1)
        self.start()

    def shutdown(self):
        self.running = False
        self.kill()

    @property
    def internal_fahrenheit(self):
        return 1.8 * self.internal_temp + 32

    @property
    def external_fahrenheit(self):
        return 1.8 * self.external_temp + 32

    def _run(self):
        self.running = True
        while self.running:
            gevent.socket.wait_read(self.serial.fileno())
            line = self.serial.readline()
            if not line:
                continue

            data = json.loads(line)
            for key, val in data.iteritems():
                setattr(self, key, val)
