import json
import logging
import os
import sys
import time

import gevent
import gevent.subprocess as subprocess

this_dir = os.path.abspath(os.path.dirname(__file__))
dht22_bin = os.path.join(this_dir, 'build/dht22')

PINS = {}
p = 0
for header in (8, 9):
    for pin in range(1, 47):
        PINS['P%d_%d' % (header, pin)] = p
        p += 1

class DHT22(object):
    pin = str(PINS['P8_17'])
    temp = 0
    humidity = 0

    def __init__(self):
        self.running = False
        self.log = logging.getLogger('dht22')
        gevent.spawn(self.dht22_loop)

    def fahrenheit(self):
        return 1.8 * self.temp + 32

    def update(self):
        try:
            args = [dht22_bin, '-p', self.pin]
            result = subprocess.check_output(args)
            data = json.loads(result)
            if data.get('status') != 'ok':
                self.log.warn('Failed to read temp sensor, will try again')
                return

            result = data.get('result')
            if not result:
                return

            self.temp = result['temperature']
            self.humidity = result['humidity']
        except subprocess.CalledProcessError, e:
            return

    def dht22_loop(self):
        self.running = True
        while self.running:
            self.update()
            gevent.sleep(10)
