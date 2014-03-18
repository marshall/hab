from gevent import monkey; monkey.patch_all()

import calendar
import datetime
import math
import os
import sys
import time
import unittest

from mock import patch, MagicMock, call, mock_open

this_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(this_dir))

class MockPepper2Modules(object):
    def __init__(self, *extra_modules):
        self.Adafruit_BBIO = MagicMock()
        self.serial = MagicMock()
        self.bluetooth = MagicMock()
        self.spidev = MagicMock()
        self.subprocess = MagicMock()

        self.modules = {
            'Adafruit_BBIO': self.Adafruit_BBIO,
            'Adafruit_BBIO.GPIO': self.Adafruit_BBIO.GPIO,
            'Adafruit_BBIO.UART': self.Adafruit_BBIO.UART,
            'Adafruit_BBIO.SPI': self.Adafruit_BBIO.SPI,
            'bluetooth': self.bluetooth,
            'serial': self.serial,
            'subprocess': self.subprocess,
            'spidev': self.spidev,
        }

        for module in extra_modules:
            self.patch_module(module)

    def patch_module(self, name):
        module = MagicMock()
        setattr(self, name, module)
        self.modules[name] = module

    def patch(self):
        return patch.dict('sys.modules', self.modules)

class NonNativeTestCase(unittest.TestCase):
    def setUp(self):
        self.modules = MockPepper2Modules()
        self.patcher = self.modules.patch()
        self.patcher.start()
        import pepper2, pepper2.droid, pepper2.screen, pepper2.obc, \
               pepper2.proto, pepper2.log, pepper2.temperature, \
               pepper2.temperature.dht22, pepper2.temperature.ds18b20, \
               pepper2.radio

        self.pepper2 = pepper2
        self.pepper2.log.setup(None)
        self.addCleanup(self.patcher.stop)

class OBCTest(NonNativeTestCase):
    def setUp(self):
        super(OBCTest, self).setUp()
        self.modules.serial.Serial.return_value.readline = lambda: None
        self.modules.bluetooth.find_service.return_value = [{'host':'localhost', 'port':999}]
        self.modules.bluetooth.BluetoothSocket.return_value.recv = lambda *args: time.sleep(150)
        self.modules.subprocess.check_output.return_value = '{"uptime": 1147,"total_procs": 100,"cpu_usage": 1.2,"total_mem": 510840,"free_mem": 296748}'
        self.obc = self.pepper2.obc.OBC()

    @patch('pepper2.obc.time.time')
    def test_uptime(self, mock_time):
        mock_time.return_value = 0
        obc = self.pepper2.obc.OBC()
        obc.uptime.work()
        self.assertEqual(obc.uptime.as_dict(), dict(hours=0, minutes=0, seconds=0))

        mock_time.return_value = 1
        obc.uptime.work()
        self.assertEqual(obc.uptime.as_dict(), dict(hours=0, minutes=0, seconds=1))

        mock_time.return_value = 3901
        obc.uptime.work()
        self.assertEqual(obc.uptime.as_dict(), dict(hours=1, minutes=5, seconds=1))

    @unittest.skip('need to recode when new algorithm is done')
    @patch('pepper2.obc.OBC.on_landed')
    @patch('pepper2.obc.OBC.on_descent')
    @patch('pepper2.obc.OBC.on_ascent')
    def test_mode(self, on_ascent, on_descent, on_landed):
        self.assertEqual(self.obc.mode, self.obc.mode_preflight)

        # no new locations
        self.obc.maybe_update_mode()
        self.assertEqual(self.obc.mode, self.obc.mode_preflight)

        self.obc.gps.fixes = [
            (0, 0, 0.1),
            (0, 0, 0.11),
            (0, 0, 0.13),
            (0, 0, 0.15),
            (0, 0, 0.2)]

        self.obc.maybe_update_mode()
        self.assertEqual(self.obc.mode, self.obc.mode_ascent)
        self.assertTrue(on_ascent.called)

        self.obc.gps.fixes = [
            (0, 0, 0.2),
            (0, 0, 0.15),
            (0, 0, 0.13),
            (0, 0, 0.11),
            (0, 0, 0.1)]
        self.obc.maybe_update_mode()
        self.assertEqual(self.obc.mode, self.obc.mode_descent)
        self.assertTrue(on_descent.called)

        self.obc.gps.fixes = [
            (0, 0, 0.1),
            (0, 0, 0.1001),
            (0, 0, 0.1002),
            (0, 0, 0.1001),
            (0, 0, 0.1002)]
        self.obc.maybe_update_mode()
        self.assertEqual(self.obc.mode, self.obc.mode_landed)
        self.assertTrue(on_landed.called)

    def test_send_telemetry(self):
        proto = self.pepper2.proto

        self.obc.droid = MagicMock(telemetry=[proto.DroidTelemetryMsg.from_data(battery=100)])
        self.obc.gps = MagicMock(latitude=100)
        self.obc.sys = MagicMock(cpu_usage=100, free_mem=100*1024)
        self.obc.radio = MagicMock()

        self.obc.work()
        self.assertEqual(len(self.obc.radio.write.mock_calls), 3)

        def getWriteBuf(i):
            return self.obc.radio.write.mock_calls[i][1][0]

        def assertMsgType(i, msg_type):
            buf = getWriteBuf(i)
            self.assertTrue(isinstance(buf, buffer))
            self.assertEqual(buf[0:2], '\x9d\x9a')
            return self.assertEqual(msg_type, ord(buf[2]))

        assertMsgType(0, proto.DroidTelemetryMsg.TYPE)
        assertMsgType(1, proto.TelemetryMsg.TYPE)
        assertMsgType(2, proto.LocationMsg.TYPE)

        droid_telemetry = proto.DroidTelemetryMsg(buf=getWriteBuf(0))
        telemetry = proto.TelemetryMsg(buf=getWriteBuf(1))
        location = proto.LocationMsg(buf=getWriteBuf(2))

        self.assertEqual(droid_telemetry.battery, 100)
        self.assertEqual(location.latitude, 100)
        self.assertEqual(telemetry.cpu_usage, 100)
        self.assertEqual(telemetry.free_mem, 100)

    '''def test_sys_update_time(self):
        self.obc.sys.update_stats = MagicMock()
        self.obc.sys.set_time = MagicMock(return_value=True)

        gps_time = datetime.datetime(year=2014, month=1, day=2, hour=3, minute=4, second=5)
        self.obc.sensors = MagicMock(is_gps_time_valid=lambda: True,
                                     gps_time=gps_time)

        self.assertFalse(self.obc.sys.time_set)
        self.obc.sys.maybe_update_time()

        self.obc.sys.set_time.assert_called_with('2014-01-02', '03:04:05')
        self.assertTrue(self.obc.sys.time_set)
        self.assertEqual(self.obc.begin, calendar.timegm(gps_time.utctimetuple()))'''


class PanelTest(NonNativeTestCase):
    def setUp(self):
        super(PanelTest, self).setUp()
        self.mock_screen = MagicMock(font_width=5, font_height=8, height=32)
        now = datetime.datetime.now()
        self.now_str = now.strftime('%m/%d %H:%M')
        self.now_mini_str = now.strftime('%H:%M')
        self.template_args = dict(
            int_temp=100.12,
            int_humidity=23,
            gps=MagicMock(quality=2, latitude=33.134, longitude=-98.333, altitude=0.123, speed=2, satellites=1),
            droid=MagicMock(connected=True),
            obc=MagicMock(uptime=MagicMock(hours=1, minutes=1, seconds=1)),
            sys=MagicMock(cpu_usage=1.2, free_mem=32768, free_mem_mb=32),
            now=now,
        )

    def test_sys_panel(self):
        panel = self.pepper2.screen.SysPanel(self.mock_screen)
        panel.template_args = self.template_args
        panel.do_draw(0, 0)

        self.mock_screen.draw_text.assert_has_calls([
            call(0, 1, 'SYS', size=2),
            call(0, 21, self.now_mini_str, size=1),
            call(37, 0, '+100F 23%'),
            call(37, 8, 'CPU 1.2%'),
            call(37, 16, 'MEM 32MB free'),
            call(37, 24, 'UP  01h 01m 01s')
        ])

class PanelBufferTest(NonNativeTestCase):
    def setUp(self):
        super(PanelBufferTest, self).setUp()
        self.obc = MagicMock()
        self.obc.cpu_usage = 50
        self.obc.gps.quality = 2
        self.obc.gps.latitude = 33.1234
        self.obc.gps.longitude = -98.1234
        self.obc.gps.altitude = 0.123
        self.obc.droid.connected = False

    @patch('pepper2.screen.time.sleep')
    @patch('pepper2.screen.GPSPanel')
    @patch('pepper2.screen.SysPanel')
    def test_switch_screen(self, SysPanel, GPSPanel, mock_sleep):
        sys_panel = SysPanel.return_value
        gps_panel = GPSPanel.return_value

        oled = self.pepper2.screen.Screen(self.obc)
        panel_buffer = oled.panel_buffer
        oled.set_start_line = MagicMock()

        self.assertEqual(panel_buffer.active_panel, sys_panel)
        self.assertEqual(panel_buffer.inactive_panel, gps_panel)

        for screen in (sys_panel, gps_panel):
            screen.template_args = oled.build_template_args()

        panel_buffer.draw()
        sys_panel.do_draw.assert_called_with(0, 0)
        gps_panel.do_draw.assert_called_with(0, 32)

        panel_buffer.switch_panel(gps_panel)
        self.assertEqual(panel_buffer.active_panel, gps_panel)
        self.assertEqual(panel_buffer.inactive_panel, sys_panel)

        gps_panel.do_draw.assert_not_called()
        oled.set_start_line.assert_has_calls([call(i) for i in range(0, 33)])

        panel_buffer.draw()
        sys_panel.do_draw.assert_called_with(0, 0)
        gps_panel.do_draw.assert_called_with(0, 32)

if __name__ == '__main__':
    unittest.main()
