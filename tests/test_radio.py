import gevent

from mock import MagicMock

from test_pepper2 import NonNativeTestCase

class TCPRadioTest(NonNativeTestCase):
    def test_two_way(self):
        server_handler = MagicMock()
        client_handler = MagicMock()

        server = self.pepper2.radio.TCPServerRadio(handler=server_handler)
        server.start()
        gevent.sleep(0.1)

        self.assertTrue(server.server is not None)

        client = self.pepper2.radio.TCPRadio(handler=client_handler, host='127.0.0.1')
        client.start()
        gevent.sleep(0.1)

        self.assertTrue(server.worker is not None)
        self.assertTrue(client.socket is not None)

        msg = self.pepper2.proto.TelemetryMsg.from_data()
        client.write(msg.as_buffer())

        gevent.sleep(0.2)
        self.assertTrue(server_handler.called)
