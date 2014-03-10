import json

from mock import patch, MagicMock

from test_pepper2 import MockPepper2Modules, NonNativeTestCase

class DHT22Test(NonNativeTestCase):
    def test_update(self):
        dht22_pkg = self.pepper2.temperature.dht22
        mock_subprocess = dht22_pkg.subprocess = MagicMock()
        mock_gevent = dht22_pkg.gevent = MagicMock()

        result = {}
        def update_result(**kwargs):
            result.update(**kwargs)
            mock_subprocess.check_output.return_value = json.dumps(result)

        dht22 = self.pepper2.temperature.DHT22()
        update_result(status='ok', result=dict(temperature=1.23, humidity=23))
        dht22.work()

        self.assertEqual(dht22.temp, 1.23)
        self.assertEqual(dht22.humidity, 23)

        update_result(status='error', result=dict(temperature=2.34, humidity=43))
        dht22.work()

        self.assertEqual(dht22.temp, 1.23)
        self.assertEqual(dht22.humidity, 23)
