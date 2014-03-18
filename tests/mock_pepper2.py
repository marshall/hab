import argparse
import collections
import gevent
from mock import patch, MagicMock
import os
import sys
import time

this_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.extend([this_dir, os.path.dirname(this_dir)])

from test_pepper2 import MockPepper2Modules

class MockPepper2(object):
    mock_stats = collections.deque([
        '{"uptime": 1147,"total_procs": 100,"cpu_usage": 1.2,"total_mem": 510840,"free_mem": 296748}\n',
        '{"uptime": 1148,"total_procs": 101,"cpu_usage": 1.9,"total_mem": 510840,"free_mem": 29674}\n',
        '{"uptime": 1149,"total_procs": 102,"cpu_usage": 8.2,"total_mem": 510840,"free_mem": 126748}\n',
        '{"uptime": 1150,"total_procs": 99,"cpu_usage": 11.2,"total_mem": 510840,"free_mem": 6748}\n',
        ])

    mock_temp = collections.deque([
        21.0, 21.4, 22.3, 29.9, -10.1, -20.2, -30.3
    ])
    mock_humidity = collections.deque([
        12, 43, 92, 100, 73
    ])
    mock_gps = collections.deque([
        '$GPGGA,040552.000,3309.3605,N,09702.0045,W,1,11,0.81,164.9,M,-24.0,M,,*54',
        '$GPRMC,040552.000,A,3309.3605,N,09702.0045,W,0.28,42.54,220114,,,A*47',
    ])

    def __init__(self):
        self.modules = MockPepper2Modules()
        self.patcher = self.modules.patch()
        self.patcher.start()
        import pepper2, pepper2.log, pepper2.proto, pepper2.temperature
        self.pepper2 = pepper2

        self.modules.bluetooth.find_service.return_value = [{'host':'localhost', 'port':999}]
        self.modules.subprocess.check_output = self.mock_rotate_get(self.mock_stats)
        self.modules.serial.Serial.return_value.readline = self.mock_rotate_get(self.mock_gps)
        pepper2.droid.DroidBluetooth = MagicMock()
        pepper2.droid.DroidBluetooth.return_value.start = lambda: gevent.spawn_later(5, self.mock_bluetooth)
        pepper2.droid.DroidBluetooth.return_value.connected = True
        pepper2.temperature.DHT22 = MagicMock()
        dht22 = pepper2.temperature.DHT22.return_value
        dht22.fahrenheit = lambda: 1.8*dht22.temp+32
        pepper2.temperature.DS18B20 = MagicMock()
        ds18b20 = pepper2.temperature.DS18B20.return_value
        ds18b20.fahrenheit = lambda: 1.8*ds18b20.temp+32
        self.build_mock_droid()

    def build_mock_droid(self):
        proto = self.pepper2.proto
        self.mock_droid = collections.deque([
            proto.DroidTelemetryMsg.from_data(battery=71, radio_dbm=-71,
                                              radio_bars=0, accel_state=0,
                                              accel_duration=0, photo_count=0,
                                              latitude=33.15592, longitude=-97.03347),
            proto.DroidTelemetryMsg.from_data(battery=81, radio_dbm=-81,
                                              radio_bars=25, accel_state=0,
                                              accel_duration=0, photo_count=0,
                                              latitude=33.15590, longitude=-97.03247),
            proto.DroidTelemetryMsg.from_data(battery=91, radio_dbm=-100,
                                              radio_bars=50, accel_state=0,
                                              accel_duration=0, photo_count=0,
                                              latitude=33.13592, longitude=-97.13347),
            proto.DroidTelemetryMsg.from_data(battery=100, radio_dbm=-100,
                                              radio_bars=75, accel_state=0,
                                              accel_duration=0, photo_count=0,
                                              latitude=33.13592, longitude=-97.13347),
        ])


    def mock_rotate_get(self, deque):
        return lambda *args, **kwargs: self.rotate_get(deque)

    def rotate_get(self, deque):
        o = deque[0]
        deque.rotate(1)
        return o

    def mock_bt_recv(self, amt):
        gevent.sleep(5)
        return 'abc'

    def mock_bluetooth(self):
        next_msg = self.rotate_get(self.mock_droid)
        self.obc.droid.handle_message(next_msg)
        gevent.spawn_later(5, self.mock_bluetooth)

    def mock_temps(self):
        self.obc.dht22.temp = self.rotate_get(self.mock_temp)
        self.obc.dht22.humidity = self.rotate_get(self.mock_humidity)
        self.obc.ds18b20.temp = self.rotate_get(self.mock_temp)
        gevent.spawn_later(5, self.mock_temps)

    def main_loop(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--screen', default=None, help='Set active screen')
        args = parser.parse_args()

        import mock_oled
        self.pepper2.log.setup(None)
        self.obc = self.pepper2.obc.OBC()
        self.obc.screen.oled = mock_oled.MockOLED()
        self.obc.screen.oled.begin()

        if args.screen == 'droid':
            self.obc.screen.auto_switch = False
            gevent.spawn(lambda: self.obc.screen.switch_panel(2))

        gevent.spawn(self.mock_temps)

        self.obc.start()
        self.obc.join()
        #self.obc.main_loop()

    def __del__(self):
        self.patcher.stop()

if __name__ == '__main__':
    MockPepper2().main_loop()
