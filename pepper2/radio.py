import logging
import socket

import Adafruit_BBIO.UART as UART
import gevent
from gevent.server import StreamServer

from pynmea import nmea
import serial

import proto

class Radio(object):
    uart = 'UART5'
    port = '/dev/ttyO5'
    baud = 9600

    def __init__(self, obc):
        self.log = logging.getLogger('radio')
        self.obc = obc
        self.setup_radio()
        self.running = False
        self.connected = False
        self.address = '?'
        self.version_info = '?'
        self.power_level = 0
        gevent.spawn(self.radio_loop)

    def shutdown(self):
        self.running = False

    def setup_radio(self):
        UART.setup(self.uart)
        self.serial = serial.Serial(port=self.port,
                                    baudrate=self.baud,
                                    timeout=1)

        result = self.send_AT('+++')
        if len(result) > 0 and result[0] == 'OK':
            self.connected = True

        result = self.send_AT('ATMY\r')
        if len(result) > 0:
            self.address = result[0]

        result = self.send_AT('ATVL\r')
        if len(result) > 0:
            result.remove('OK')
            self.version_info = '/'.join(result)

        result = self.send_AT('ATPL\r')
        if len(result) > 0:
            self.power_level = int(result[0])

        self.send_AT('ATCN\r')
        self.log.info('connected=%s, address=%s, version_info=%s, power_level=%d',
                      self.connected, self.address, self.version_info, self.power_level)

    def read_AT_line(self):
        response = []
        while True:
            c = self.serial.read(1)
            if c is None or c[0] == '\r':
                break
            response.append(c[0])

        if len(response) > 0:
            return ''.join(response)

        return None

    def send_AT(self, cmd):
        self.serial.write(cmd)
        responses = []
        response = []
        try:
            gevent.socket.wait_read(self.serial.fileno(), timeout=5)
            while self.serial.inWaiting() > 0:
                response = self.read_AT_line()
                if response:
                    responses.append(response)
        except socket.timeout, e:
            pass

        return responses

    def write_line(self, str):
        self.log.info(str)
        self.write(str + '\r\n')

    def write(self, str):
        gevent.socket.wait_write(self.serial.fileno())
        self.serial.write(str)

    def next_msg(self, f):
        try:
            msg = proto.MsgReader().read(f)
            if msg:
                self.handle_msg(msg)
        except (proto.BadMarker, proto.BadChecksum, proto.BadMsgType) as e:
            # These are logged in proto for now
            pass

    def handle_msg(self, msg):
        # TODO handle msg
        # self.obc.droid.set_photo_index(sentence.photo_index)
        pass

    def radio_loop(self):
        self.running = True
        while self.running:
            gevent.socket.wait_read(self.serial.fileno())
            self.next_msg(self.serial)

class TCPRadio(Radio):
    def shutdown(self):
        super(TCPRadio, self).shutdown()
        if self.socket:
            self.socket.close()
        self.server.stop()

    def setup_radio(self):
        self.server = StreamServer(('0.0.0.0', 12345), self.connection)
        self.socket = None

    def write(self, str):
        if not self.socket:
            return

        try:
            self.socket.send(str)
        except socket.error, e:
            self.socket = None

    def connection(self, socket, addr):
        self.socket = socket
        f = socket.makefile()
        while self.running:
            self.next_msg(f)

    def radio_loop(self):
        self.server.serve_forever()
