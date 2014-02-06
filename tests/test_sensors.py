from gevent import monkey; monkey.patch_all()

from datetime import datetime
import json
import os
import sys
import time
import unittest

from mock import patch, MagicMock, call, mock_open

this_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(this_dir))

from test_pepper2 import MockPepper2Modules, NonNativeTestCase

class SensorsTest(NonNativeTestCase):
    def setUp(self):
        super(SensorsTest, self).setUp()
        self.pepper2.sensors.gevent = MagicMock()

    def build_sensor_data(self, **kwargs):
        serial_obj = self.modules.serial.Serial.return_value
        serial_obj.readline.return_value = json.dumps(kwargs)

    def test_attrs(self):
        sensors = self.pepper2.sensors.Sensors(autostart=False)
        self.assertEqual(sensors.internal_temp, 0)
        self.assertEqual(sensors.internal_fahrenheit, 0)
        self.assertEqual(sensors.internal_humidity, 0)
        self.assertEqual(sensors.external_temp, 0)
        self.assertEqual(sensors.external_fahrenheit, 0)
        self.assertEqual(sensors.external_humidity, 0)
        self.assertEqual(sensors.gps_latitude, 0)
        self.assertEqual(sensors.gps_longitude, 0)
        self.assertEqual(sensors.gps_altitude, 0)
        self.assertEqual(sensors.gps_quality, 0)
        self.assertEqual(sensors.gps_speed, 0)
        self.assertEqual(sensors.gps_satellites, 0)
        self.assertEqual(sensors.gps_time, None)

    def test_update_data(self):
        sensors = self.pepper2.sensors.Sensors(autostart=False)
        line = json.dumps(dict(internal_temp=20,
                               external_temp=30,
                               internal_humidity=25,
                               external_humidity=35,
                               gps_latitude=1.234,
                               gps_longitude=-2.345,
                               gps_altitude=234.5,
                               gps_quality=3,
                               gps_speed=4,
                               gps_satellites=5,
                               gps_timestamp='2014-02-01 01:02:03'))

        sensors.update_data(line)

        self.assertEqual(sensors.internal_temp, 20)
        self.assertEqual(sensors.internal_fahrenheit, 68)
        self.assertEqual(sensors.external_temp, 30)
        self.assertEqual(sensors.external_fahrenheit, 86)
        self.assertEqual(sensors.internal_humidity, 25)
        self.assertEqual(sensors.external_humidity, 35)
        self.assertEqual(sensors.gps_latitude, 1.234)
        self.assertEqual(sensors.gps_longitude, -2.345)
        self.assertEqual(sensors.gps_altitude, 234.5)
        self.assertEqual(sensors.gps_quality, 3)
        self.assertEqual(sensors.gps_speed, 4)
        self.assertEqual(sensors.gps_satellites, 5)

        self.assertEqual(sensors.gps_time, datetime(year=2014, month=2, day=1,
                                                    hour=1, minute=2, second=3))
        self.assertTrue(sensors.is_gps_time_valid())

    def test_update_gps_time(self):
        sensors = self.pepper2.sensors.Sensors(autostart=False)
        bad_time = json.dumps(dict(gps_timestamp='2000-01-01 01:02:03'))
        sensors.update_data(bad_time)

        self.assertFalse(sensors.is_gps_time_valid())
        self.assertEqual(sensors.gps_time, datetime(year=2000, month=1, day=1,
                                                    hour=1, minute=2, second=3))

        sensors.update_data(json.dumps(dict(gps_timestamp='2014-01-01 02:03:04')))
        self.assertTrue(sensors.is_gps_time_valid())
        self.assertEqual(sensors.gps_time, datetime(year=2014, month=1, day=1,
                                                    hour=2, minute=3, second=4))

        # only time should be updated if we already have an accurate date
        sensors.update_data(bad_time)
        self.assertTrue(sensors.is_gps_time_valid())
        self.assertEqual(sensors.gps_time, datetime(year=2014, month=1, day=1,
                                                    hour=1, minute=2, second=3))
