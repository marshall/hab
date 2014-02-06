from datetime import datetime
import logging
import json

import gevent
import serial

from Adafruit_BBIO import UART

class Sensors(gevent.Greenlet):
    uart = 'UART1'
    port = '/dev/ttyO1'
    baud = 115200

    def __init__(self, autostart=True):
        super(Sensors, self).__init__()
        self.log = logging.getLogger('sensors')
        self.internal_temp = self.internal_fahrenheit = self.internal_humidity = 0
        self.external_temp = self.external_fahrenheit = self.external_humidity = 0
        self.gps_latitude = self.gps_longitude = 0
        self.gps_altitude = self.gps_quality = 0
        self.gps_speed = self.gps_satellites = 0
        self.gps_time = None

        self.running = False
        UART.setup(self.uart)

        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=1)
        if autostart:
            self.start()

    def shutdown(self):
        self.running = False
        self.kill()

    def is_gps_time_valid(self, gps_time=None):
        if not gps_time:
            gps_time = self.gps_time

        # It's 2014, so > 2013 is a good heuristic right?
        return gps_time is not None and gps_time.year > 2013

    def handle_gps_timestamp(self, key, timestamp):
        if not timestamp:
            return

        # strip off the milliseconds
        parts = timestamp.split('.')
        if len(parts) == 2:
            timestamp = parts[0]

        timestamp = timestamp.replace('2000-00-00', '2000-01-01')
        new_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        # oddly enough the gps lib gets the right date only part of the time
        # then updates time but properly. so we account for this here (I know,
        # it's a hack)

        if not self.is_gps_time_valid():
            if self.is_gps_time_valid(new_time):
                self.log.info('First valid GPS time: %s', timestamp)

            self.gps_time = new_time
            return

        self.gps_time = self.gps_time.replace(hour=new_time.hour,
                                              minute=new_time.minute,
                                              second=new_time.second)

    def handle_temp(self, key, temp):
        setattr(self, key, temp)
        setattr(self, key.replace('_temp', '_fahrenheit'), 1.8 * temp + 32)

    handle_internal_temp = handle_temp
    handle_external_temp = handle_temp

    def handle_data(self, key, value):
        setattr(self, key, value)

    def update_data(self, line):
        data = json.loads(line)
        for key, value in data.iteritems():
            handler = getattr(self, 'handle_' + key, self.handle_data)
            handler(key, data[key])

    def _run(self):
        self.running = True
        while self.running:
            gevent.socket.wait_read(self.serial.fileno())
            line = self.serial.readline()
            if not line:
                continue

            self.update_data(line)

