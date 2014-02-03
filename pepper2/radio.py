import logging

import Adafruit_BBIO.UART as UART
import gevent
from gevent.server import StreamServer

from pynmea import nmea
import serial

@nmea.nmea_sentence
class PPR2SP(nmea.NMEASentence):
    ''' PEPPER-2 set photo command
        relays the actively streaming photo index to the android device
    '''

    def __init__(self):
        parse_map = (('Photo Index', 'photo_index'))
        super(PPR2SP, self).__init__(parse_map)

class Radio(object):
    uart = 'UART5'
    port = '/dev/ttyO5'
    baud = 9600

    def __init__(self, obc):
        self.logger = logging.getLogger('radio')
        self.obc = obc
        self.setup_radio()
        gevent.spawn(self.radio_loop)

    def setup_radio(self):
        UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=1)

    def write_line(self, str):
        self.logger.info(str)
        self.write(str + '\r\n')

    def write(self, str):
        gevent.socket.wait_write(self.serial.fileno())
        self.serial.write(str)

    def radio_loop(self):
        while True:
            gevent.socket.wait_read(self.serial.fileno())
            sentence = nmea.parse_sentence(self.serial.readline())
            if isinstance(sentence, PPR2SP):
                self.obc.droid.set_photo_index(sentence.photo_index)

class TCPRadio(Radio):
    def setup_radio(self):
        self.server = StreamServer(('0.0.0.0', 12345), self.connection)
        self.socket = None

    def write(self, str):
        if not self.socket:
            return
        self.socket.send(str)

    def connection(self, socket, addr):
        self.socket = socket
        f = socket.makefile()
        while True:
            sentence = nmea.parse_sentence(f.readline())
            if isinstance(sentence, PPR2SP):
                self.obc.droid.set_photo_index(sentence.photo_index)

    def radio_loop(self):
        self.server.serve_forever()
