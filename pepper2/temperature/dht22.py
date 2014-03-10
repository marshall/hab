import json
import logging
import os
import sys
import time

import gevent
import gevent.subprocess as subprocess

import pepper2

this_dir = os.path.abspath(os.path.dirname(__file__))
dht22_bin = os.path.join(this_dir, 'build/dht22')

PINS = {}
p = 0
for header in (8, 9):
    for pin in range(1, 47):
        PINS['P%d_%d' % (header, pin)] = p
        p += 1

class DHT22(pepper2.Worker):
    worker_interval = 10

    pin = str(PINS['P8_17'])
    temp = 0
    humidity = 0

    def fahrenheit(self):
        return 1.8 * self.temp + 32

    def work(self):
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
