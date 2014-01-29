import collections
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

    mock_gps = collections.deque([
        '$GPGGA,040552.000,3309.3605,N,09702.0045,W,1,11,0.81,164.9,M,-24.0,M,,*54',
        '$GPRMC,040552.000,A,3309.3605,N,09702.0045,W,0.28,42.54,220114,,,A*47',
    ])

    mock_droid = collections.deque([
        ('T', '71.0,0,1,0,0,33.15592,-97.03347,0.0'),
        ('T', '77.0,0,4,0,10,33.15591,-97.03346,0.0'),
        ('T', '85.0,0,9,0,19,33.15611,-97.0334,0.0'),
    ])

    def __init__(self):
        self.modules = MockPepper2Modules()
        self.patcher = self.modules.patch()
        self.patcher.start()
        import pepper2
        self.pepper2 = pepper2
        self.modules.bluetooth.find_service.return_value = [{'host':'localhost', 'port':999}]
        self.modules.bluetooth.BluetoothSocket.return_value.recv = self.mock_bt_recv
        self.modules.subprocess.check_output = self.mock_rotate_get(self.mock_stats)
        self.modules.serial.Serial.return_value.readline = self.mock_rotate_get(self.mock_gps)

    def mock_rotate_get(self, deque):
        return lambda *args, **kwargs: self.rotate_get(deque)

    def rotate_get(self, deque):
        o = deque[0]
        deque.rotate(1)
        return o

    def mock_bt_recv(self, amt):
        time.sleep(5)
        return 'abc'

    def mock_bt_handle(self, data):
        next_msg = self.rotate_get(self.mock_droid)
        msg_type = self.obc.droid.msg_telemetry
        if next_msg[0] == 'PD':
            msg_type = self.obc.droid.msg_photo_data

        self.obc.droid.handle_message(len(next_msg[1]), msg_type,
                                      self.obc.droid.checksum(next_msg[1]),
                                      next_msg[1])

    def main_loop(self):
        import mock_oled
        self.obc = self.pepper2.OBC()
        self.obc.screen.oled = mock_oled.MockOLED()
        self.obc.screen.oled.begin()
        self.obc.droid.droid_bt.handle_data = self.mock_bt_handle
        self.obc.main_loop()

    def __del__(self):
        self.patcher.stop()

if __name__ == '__main__':
    MockPepper2().main_loop()
