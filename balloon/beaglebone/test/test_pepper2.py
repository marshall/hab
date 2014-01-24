import math
from mock import patch, MagicMock, call
import os
import sys
import time
import unittest

this_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(this_dir))

class MockPepper2Modules(object):
    def __init__(self):
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
        self.modules.subprocess.check_output.return_value = '5.3\n265320k\n'

    @patch('pepper2.time.time')
    def test_uptime(self, mock_time):
        mock_time.return_value = 0
        obc = self.pepper2.OBC()
        obc.sensor_update()
        self.assertEqual(obc.get_uptime(), dict(hours=0, minutes=0, seconds=0))

        mock_time.return_value = 1
        obc.sensor_update()
        self.assertEqual(obc.get_uptime(), dict(hours=0, minutes=0, seconds=1))

        mock_time.return_value = 3901
        obc.sensor_update()
        self.assertEqual(obc.get_uptime(), dict(hours=1, minutes=5, seconds=1))

    @patch('pepper2.OBC.on_landed')
    @patch('pepper2.OBC.on_descent')
    @patch('pepper2.OBC.on_ascent')
    def test_mode(self, on_ascent, on_descent, on_landed):
        obc = self.pepper2.OBC()
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
        obc = self.pepper2.OBC()

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

        gps = self.pepper2.GPS()
        serial_write.assert_has_calls([call(self.pepper2.GPS.init_sentences[0] + '\r\n'),
                                       call(self.pepper2.GPS.init_sentences[1] + '\r\n')])

    def test_gpgga(self):
        serial_readline = self.modules.serial.Serial.return_value.readline
        serial_readline.return_value = \
            '$GPGGA,040552.000,3309.3605,N,09702.0045,W,1,11,0.81,164.9,M,-24.0,M,,*54'

        gps = self.pepper2.GPS()
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

        gps = self.pepper2.GPS()
        gps.update()

        self.assertEqual(gps.gprmc, serial_readline.return_value)
        self.assertEqual(len(gps.fixes), 0)

    def test_telemetry(self):
        serial_readline = self.modules.serial.Serial.return_value.readline
        gps = self.pepper2.GPS()

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

class ScreenTest(NonNativeTestCase):
    def test_main_screen(self):
        oled = MagicMock()
        oled.oled.font.cols = 5
        oled.oled.font.rows = 8
        oled.oled.rows = 32
        screen = self.pepper2.MainScreen(oled)
        screen.template_args = dict(
            current_time='0',
            hours=1, minutes=1, seconds=1,
            android='Y', radio='Y',
            gps_qual=2, tmp=100.12,
            gps_lat=33.134, gps_lng=-98.333,
            gps_alt=0.123
        )
        screen.do_draw(0, 0)

        oled.draw_text.assert_has_calls([
            call(0, 0, '0 01h01m01s', invert=True),
            call(0, 8, 'AND:Y RDO:Y GPS:2'),
            call(0, 16, 'TMP:+100.12F LAT:+33.1'),
            call(0, 24, 'LNG:-98.3 ALT:+0.1K')])

class ScreenBufferTest(NonNativeTestCase):
    def setUp(self):
        super(ScreenBufferTest, self).setUp()
        self.obc = MagicMock()
        self.obc.cpu_usage = 50
        self.obc.gps.quality = 2
        self.obc.gps.latitude = 33.1234
        self.obc.gps.longitude = -98.1234
        self.obc.gps.altitude = 0.123
        self.obc.get_uptime.return_value = dict(hours=1,minutes=1,seconds=1)
        self.obc.droid.connected = False

    @patch('pepper2.time.sleep')
    @patch('pepper2.GPSScreen')
    @patch('pepper2.SysScreen')
    @patch('pepper2.MainScreen')
    def test_switch_screen(self, MainScreen, SysScreen, GPSScreen, mock_sleep):
        main_screen = MainScreen.return_value
        sys_screen = SysScreen.return_value
        gps_screen = GPSScreen.return_value

        oled = self.pepper2.OLED(self.obc)
        screen_buffer = oled.screen_buffer
        screen_buffer.oled = MagicMock()
        screen_buffer.oled.SET_START_LINE = 0

        self.assertEqual(screen_buffer.active_screen, sys_screen)
        self.assertEqual(screen_buffer.inactive_screen, gps_screen)

        for screen in (main_screen, sys_screen, gps_screen):
            screen.template_args = oled.build_template_args()

        screen_buffer.draw()
        sys_screen.do_draw.assert_called_with(0, 0)
        gps_screen.do_draw.assert_called_with(0, 32)

        screen_buffer.switch_screen(gps_screen)
        self.assertEqual(screen_buffer.active_screen, gps_screen)
        self.assertEqual(screen_buffer.inactive_screen, sys_screen)

        gps_screen.do_draw.assert_not_called()
        screen_buffer.oled.command.assert_has_calls([call(i) for i in range(0, 33)])

        screen_buffer.draw()
        sys_screen.do_draw.assert_called_with(0, 0)
        gps_screen.do_draw.assert_called_with(0, 32)

        screen_buffer.switch_screen(main_screen)
        self.assertEqual(screen_buffer.active_screen, main_screen)
        self.assertEqual(screen_buffer.inactive_screen, gps_screen)
        self.assertTrue(sys_screen not in screen_buffer.screens)
        self.assertEqual(len(screen_buffer.screens), 2)

        main_screen.do_draw.assert_called_with(0, 0)
        screen_buffer.oled.command.assert_has_calls([call(i) for i in range(32, -1, -1)])

        screen_buffer.draw()
        main_screen.do_draw.assert_called_with(0, 0)
        gps_screen.do_draw.assert_called_with(0, 32)

if __name__ == '__main__':
    unittest.main()
