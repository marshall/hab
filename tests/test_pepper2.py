from gevent import monkey; monkey.patch_all()

import datetime
import math
from mock import patch, MagicMock, call, mock_open
import os
import sys
import time
import unittest

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
        import pepper2
        self.pepper2 = pepper2

        self.addCleanup(self.patcher.stop)

class OBCTest(NonNativeTestCase):
    def setUp(self):
        super(OBCTest, self).setUp()
        self.modules.serial.Serial.return_value.readline = lambda: None
        self.modules.bluetooth.find_service.return_value = [{'host':'localhost', 'port':999}]
        self.modules.bluetooth.BluetoothSocket.return_value.recv = lambda *args: time.sleep(150)
        self.modules.subprocess.check_output.return_value = '{"uptime": 1147,"total_procs": 100,"cpu_usage": 1.2,"total_mem": 510840,"free_mem": 296748}'

    @patch('pepper2.obc.time.time')
    def test_uptime(self, mock_time):
        mock_time.return_value = 0
        obc = self.pepper2.obc.OBC()
        obc.sys_update()
        self.assertEqual(obc.get_uptime(), dict(hours=0, minutes=0, seconds=0))

        mock_time.return_value = 1
        obc.sys_update()
        self.assertEqual(obc.get_uptime(), dict(hours=0, minutes=0, seconds=1))

        mock_time.return_value = 3901
        obc.sys_update()
        self.assertEqual(obc.get_uptime(), dict(hours=1, minutes=5, seconds=1))

    @patch('pepper2.obc.OBC.on_landed')
    @patch('pepper2.obc.OBC.on_descent')
    @patch('pepper2.obc.OBC.on_ascent')
    def test_mode(self, on_ascent, on_descent, on_landed):
        obc = self.pepper2.obc.OBC()
        self.assertEqual(obc.mode, obc.mode_preflight)

        # no new locations
        obc.maybe_update_mode()
        self.assertEqual(obc.mode, obc.mode_preflight)

        obc.gps.fixes = [
            (0, 0, 0.1),
            (0, 0, 0.11),
            (0, 0, 0.13),
            (0, 0, 0.15),
            (0, 0, 0.2)]

        obc.maybe_update_mode()
        self.assertEqual(obc.mode, obc.mode_ascent)
        self.assertTrue(on_ascent.called)

        obc.gps.fixes = [
            (0, 0, 0.2),
            (0, 0, 0.15),
            (0, 0, 0.13),
            (0, 0, 0.11),
            (0, 0, 0.1)]
        obc.maybe_update_mode()
        self.assertEqual(obc.mode, obc.mode_descent)
        self.assertTrue(on_descent.called)

        obc.gps.fixes = [
            (0, 0, 0.1),
            (0, 0, 0.1001),
            (0, 0, 0.1002),
            (0, 0, 0.1001),
            (0, 0, 0.1002)]
        obc.maybe_update_mode()
        self.assertEqual(obc.mode, obc.mode_landed)
        self.assertTrue(on_landed.called)

    def test_build_nmea(self):
        obc = self.pepper2.obc.OBC()

        # http://www.hhhh.org/wiml/proj/nmeaxor.html
        nmea = obc.build_nmea('ABC', '1,2,3')
        self.assertEqual(nmea, '$PPR2ABC,1,2,3*3C')

class GPSTest(NonNativeTestCase):
    def assertNear(self, val1, val2, near=0.00001):
        factor = 1 / near
        rounded_val1 = int(math.floor(val1 * factor) / factor)
        rounded_val2 = int(math.floor(val2 * factor) / factor)
        self.assertEqual(rounded_val1, rounded_val2)

    def test_init(self):
        serial_write = self.modules.serial.Serial.return_value.write

        gps = self.pepper2.gps.GPS()
        serial_write.assert_has_calls([call(self.pepper2.gps.GPS.init_sentences[0] + '\r\n'),
                                       call(self.pepper2.gps.GPS.init_sentences[1] + '\r\n')])

    def test_gpgga(self):
        serial_readline = self.modules.serial.Serial.return_value.readline
        serial_readline.return_value = \
            '$GPGGA,040552.000,3309.3605,N,09702.0045,W,1,11,0.81,164.9,M,-24.0,M,,*54'

        gps = self.pepper2.gps.GPS()
        gps.update()

        self.assertTrue(gps.gpgga is not None)
        self.assertNear(gps.latitude, 33.156008)
        self.assertNear(gps.longitude, -97.033408)
        self.assertNear(gps.altitude, 0.1649)
        self.assertEqual(len(gps.fixes), 1)

    def test_gprmc(self):
        serial_readline = self.modules.serial.Serial.return_value.readline

        # http://www.hiddenvision.co.uk/ez/
        serial_readline.return_value = \
            '$GPRMC,040552.000,A,3309.3605,N,09702.0045,W,0.28,42.54,220114,,,A*47'

        gps = self.pepper2.gps.GPS()
        gps.update()

        self.assertEqual(gps.gprmc, serial_readline.return_value)
        self.assertEqual(len(gps.fixes), 0)

    def test_telemetry(self):
        serial_readline = self.modules.serial.Serial.return_value.readline
        gps = self.pepper2.gps.GPS()

        serial_readline.return_value = \
            '$GPGGA,040552.000,3309.3605,N,09702.0045,W,1,11,0.81,164.9,M,-24.0,M,,*54'
        gps.update()

        serial_readline.return_value = \
            '$GPRMC,040552.000,A,3309.3605,N,09702.0045,W,0.28,42.54,220114,,,A*47'
        gps.update()

        self.assertTrue(gps.gpgga is not None)
        self.assertTrue(gps.gprmc is not None)
        self.assertEqual(len(gps.telemetry), 2)
        self.assertEqual(gps.telemetry[0], gps.gprmc)
        self.assertEqual(gps.telemetry[1], gps.gpgga)

class PanelTest(NonNativeTestCase):
    def setUp(self):
        super(PanelTest, self).setUp()
        self.mock_screen = MagicMock(font_width=5, font_height=8, height=32)
        now = datetime.datetime.now()
        self.now_str = now.strftime('%m/%d %H:%M')
        self.template_args = dict(
            gps=MagicMock(quality=2, latitude=33.134, longitude=-98.333, altitude=0.123),
            droid=MagicMock(connected=True),
            obc=MagicMock(uptime_hr=1, uptime_min=1, uptime_sec=1),
            temp=MagicMock(fahrenheit=100.12),
            sys=MagicMock(cpu_usage=1.2, free_mem=32768, free_mem_mb=32),
            now=now,
        )

    def test_main_panel(self):
        panel = self.pepper2.screen.MainPanel(self.mock_screen)
        panel.template_args = self.template_args
        panel.do_draw(0, 0)

        self.mock_screen.draw_text.assert_has_calls([
            call(0, 0, '%s 01h01m01s' % self.now_str, invert=True),
            call(0, 8, 'AND:1 RDO:F GPS:2'),
            call(0, 16, 'TMP:+100.12F LAT:+33.1'),
            call(0, 24, 'LNG:-98.3 ALT:+0.1K')])

    def test_sys_panel(self):
        panel = self.pepper2.screen.SysPanel(self.mock_screen)
        panel.template_args = self.template_args
        panel.do_draw(0, 0)

        self.mock_screen.draw_text.assert_has_calls([
            call(0, 1, 'SYS', size=2),
            call(0, 21, '+100F', size=1),
            call(37, 0, self.now_str),
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
        self.obc.get_uptime.return_value = dict(hours=1,minutes=1,seconds=1)
        self.obc.droid.connected = False

    @patch('pepper2.screen.time.sleep')
    @patch('pepper2.screen.GPSPanel')
    @patch('pepper2.screen.SysPanel')
    @patch('pepper2.screen.MainPanel')
    def test_switch_screen(self, MainPanel, SysPanel, GPSPanel, mock_sleep):
        main_panel = MainPanel.return_value
        sys_panel = SysPanel.return_value
        gps_panel = GPSPanel.return_value

        oled = self.pepper2.screen.Screen(self.obc)
        panel_buffer = oled.panel_buffer
        oled.set_start_line = MagicMock()

        self.assertEqual(panel_buffer.active_panel, sys_panel)
        self.assertEqual(panel_buffer.inactive_panel, gps_panel)

        for screen in (main_panel, sys_panel, gps_panel):
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

        panel_buffer.switch_panel(main_panel)
        self.assertEqual(panel_buffer.active_panel, main_panel)
        self.assertEqual(panel_buffer.inactive_panel, gps_panel)
        self.assertTrue(sys_panel not in panel_buffer.panels)
        self.assertEqual(len(panel_buffer.panels), 2)

        main_panel.do_draw.assert_called_with(0, 0)
        oled.set_start_line.assert_has_calls([call(i) for i in range(32, -1, -1)])

        panel_buffer.draw()
        main_panel.do_draw.assert_called_with(0, 0)
        gps_panel.do_draw.assert_called_with(0, 32)

class TempTest(NonNativeTestCase):
    @patch('pepper2.temp_sensor.os.path.exists')
    def test_temp_sensor(self, mock_exists):
        mock_exists.return_value = True
        with patch('pepper2.temp_sensor.open', mock_open(read_data='dht22\n'), create=True) as m:
            sensor = self.pepper2.temp_sensor.TempSensor()

        self.assertEqual(sensor.kmod_loaded, True)

        def mock_read_sysfs(path):
            if path.endswith('/temp'):
                return '23300\n'
            elif path.endswith('/humidity'):
                return '19200\n'
            return ''

        sensor.read_sysfs_file = mock_read_sysfs
        sensor.update()

        self.assertEqual(sensor.celsius, 23.3)
        self.assertEqual(sensor.fahrenheit, 73.94)
        self.assertEqual(sensor.humidity, 19.2)

if __name__ == '__main__':
    unittest.main()
