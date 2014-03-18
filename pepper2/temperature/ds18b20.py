import logging

import gevent

import pepper2

class DS18B20(pepper2.Worker):
    worker_interval = 10

    '''
    Connected to P9_28, through the W1 driver / DeviceTree overlay
    see firmware/BB-W1-00A0.dts
    '''
    sysfs_path = '/sys/bus/w1/devices/28-0000055d6f2a/w1_slave'
    temp = 0

    def fahrenheit(self):
        return 1.8 * self.temp + 32

    def work(self):
        try:
            raw = open(self.sysfs_path, 'r').read()
            self.temp = float(raw.split("t=")[-1]) / 1000.0
        except IOError, e:
            self.log.warn('Failed to read temp sensor, will try again')
