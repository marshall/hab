import math
import logging
import os
import subprocess

this_dir = os.path.abspath(os.path.dirname(__file__))

class TempSensor(object):
    def __init__(self):
        self.log = logging.getLogger('temp_sensor')
        self.celsius = 0
        self.humidity = 0
        self.kmod_loaded = False
        self.check_kernel_module()

    def check_kernel_module(self):
        if not os.path.exists('/proc/modules'):
            return

        modules = open('/proc/modules', 'rt').read()
        for line in modules.splitlines():
            if line.startswith('dht22'):
                self.kmod_loaded = True
                break

        if not self.kmod_loaded:
            self.load_kernel_module()

    def load_kernel_module(self):
        kmod_path = os.path.join(this_dir, 'dht22', 'dht22.ko')
        try:
            subprocess.check_call(['insmod', kmod_path])
            self.kmod_loaded = True
        except subprocess.CalledProcessError, e:
            self.log.error('Unable to install dht22 kernel module')

    def read_sysfs_file(self, path, tries=5):
        while tries > 0:
            try:
                f = open(path, 'r')
                data = f.readline()
                f.close()
                return data
            except Exception, e:
                tries -= 1

        return None

    def update(self):
        t = self.read_sysfs_file('/sys/devices/platform/dht22/temp')
        h = self.read_sysfs_file('/sys/devices/platform/dht22/humidity')

        if t:
            self.celsius = int(t) / 1000.0
        if h:
            self.humidity = int(h) / 1000.0

    @property
    def fahrenheit(self):
        return 1.8 * self.celsius + 32

    @property
    def dew_point(self):
        a0 = 373.15 / (273.15 + self.celsius)
        dew_sum = -7.90298 * (a0 - 1)
        dew_sum += 5.02808 * math.log10(a0)
        dew_sum += -1.3816e-7 * (pow(10, (11.344*(1-1/a0)))-1)
        dew_sum += 8.1328e-3 * (pow(10,(-3.49149*(a0-1)))-1)
        dew_sum += math.log10(1013.246)
        vp = pow(10, dew_sum - 3) * self.humidity
        t = math.log(vp / 0.61078)
        return (241.88 * t) / (17.558 - t)
