import gevent
from gevent import monkey; monkey.patch_all()

import logging

class DS18B20(object):
    '''
    Connected to P9_28, through the W1 driver / DeviceTree overlay
    see firmware/BB-W1-00A0.dts
    '''
    interval = 10
    sysfs_path = '/sys/bus/w1/devices/28-0000055d6f2a/w1_slave'
    temp = 0

    def __init__(self):
        self.running = False
        self.log = logging.getLogger('ds18b20')
        gevent.spawn(self.ds18b20_loop)

    def fahrenheit(self):
        return 1.8 * self.temp + 32

    def update(self):
        try:
            raw = open(self.sysfs_path, 'r').read()
            self.temp = float(raw.split("t=")[-1]) / 1000.0
        except IOError, e:
            self.log.warn('Failed to read temp sensor, will try again')

    def ds18b20_loop(self):
        self.running = True
        while self.running:
            self.update()
            gevent.sleep(self.interval)
