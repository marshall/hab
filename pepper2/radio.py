import base64
import logging
import socket

import gevent
import gevent.socket
from gevent.server import StreamServer

from pynmea import nmea
import serial

import proto
import worker

class Radio(worker.ProtoMsgWorker):
    def __init__(self, handler=None, port='/dev/ttyO5', baud=9600, uart='UART5',
                 power_level=4, *args, **kwargs):
        super(Radio, self).__init__(*args, **kwargs)
        self.handler = handler
        self.port = port
        self.baud = baud
        self.uart = uart
        self.power_level = power_level
        self.connected = False
        self.running = False
        self.address = '?'
        self.version_info = '?'

    def started(self):
        if self.uart:
            import Adafruit_BBIO.UART as UART
            UART.setup(self.uart)

        self.file = serial.Serial(port=self.port,
                                  baudrate=self.baud,
                                  timeout=1)

        self.log.info('Configuring radio')
        self.write('+++')
        if not self.read_OK():
            self.log.warn('Warning: skipping configuration!')
            self.connected = True
            return

        self.connected = True

        self.log.info('connected:%s. getting address', self.connected)

        self.write('ATMY\r')
        self.address = self.read_AT_line()

        self.log.info('address:%s. getting version info', self.address)
        self.write('ATVL\r')
        result = self.read_AT_lines()
        if len(result) > 0:
            if 'OK' in result:
                result.remove('OK')
            self.version_info = '/'.join(result)

        self.log.info('version_info:%s. setting power level to %d', self.version_info, self.power_level)

        self.write('ATPL %d\r' % self.power_level)
        self.read_AT_lines()

        self.write('ATPL\r')
        result = self.read_AT_lines()
        if len(result) > 0:
            self.power_level = int(result[0])

        self.write('ATCN\r')
        self.read_AT_lines()
        self.log.info('connected=%s, address=%s, version_info=%s, power_level=%d',
                      self.connected, self.address, self.version_info, self.power_level)

    def read_OK(self):
        try:
            gevent.socket.wait_read(self.file.fileno(), timeout=4)
            msg = self.file.read(3)
            return msg == 'OK\r'
        except socket.timeout, e:
            return False

        '''str = ''
        while True:
            c = self.file.read(1)
            if not c:
                continue

            str += c[0]
            if str == 'OK\r':
                return'''

    def read_AT_line(self):
        response = []
        while True:
            c = self.file.read(1)
            if c is None or len(c) == 0 or c[0] == '\r':
                break
            response.append(c[0])

        if len(response) > 0:
            return ''.join(response)

        return None

    def read_AT_lines(self):
        responses = []
        try:
            while True:
                response = self.read_AT_line()
                if not response:
                    break
                responses.append(response)
        except socket.timeout, e:
            pass

        return responses

    def write_line(self, str):
        self.log.info(str)
        self.write(str + '\r\n')

    def write(self, str):
        try:
            self.file.write(str)
            self.file.flush()
        except:
            pass

    def work(self):
        if self.handler:
            self.handler(self.msg)

        self.log.message(self.msg)

TCP_PORT = 9910
class TCPRadio(Radio):
    socket = None
    def __init__(self, host=None, socket=None, *args, **kwargs):
        super(TCPRadio, self).__init__(*args, **kwargs)
        self.host = host
        self.socket = socket
        if not socket and host:
            self.log.info('Connecting to %s' % self.host)
            self.socket = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_STREAM)
            self.socket.connect((self.host, TCP_PORT))

        self.file = self.socket.makefile()

    def started(self):
        pass

    def stopped(self):
        if self.socket:
            self.socket.close()
            self.socket = None
        self.file = None

    def write(self, str):
        if not self.socket:
            return

        try:
            self.socket.sendall(str)
        except (IOError, socket.timeout, socket.error), e:
            self.log.exception('Error sending')
            self.socket = None

class TCPServerRadio(gevent.Greenlet):
    def __init__(self, handler=None):
        super(TCPServerRadio, self).__init__()
        self.log = logging.getLogger('tcpserverradio')
        self.handler = handler
        self.server = StreamServer(('0.0.0.0', TCP_PORT), self.connection)
        self.worker = None
        self.link(self.stopped)

    def _run(self):
        self.server.serve_forever()

    def stopped(self, source):
        if self.server:
            self.server.stop()
            self.server = None
        if self.worker:
            self.worker.stop()
            self.worker = None

    def connection(self, socket, addr):
        self.log.info('Connection from %s:%d', *addr)
        if self.worker:
            self.worker.stop()

        self.worker = TCPRadio(socket=socket, handler=self.handler)
        self.worker.start()

    def write(self, str):
        if not self.worker:
            return

        self.worker.write(str)
