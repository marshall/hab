import logging
import socket
import struct
import time

import bluetooth
import gevent
from pynmea import nmea, utils

import hab_utils
import proto

log = logging.getLogger('droid')

class DroidBluetooth(gevent.Greenlet):
    daemon            = True
    bt_addr           = '0C:DF:A4:B1:D7:7A'
    service_uuid      = 'de746609-6dbf-4917-9040-40d1d2ce9c79'
    socket_timeout    = 60
    reconnect_timeout = 15

    def __init__(self, droid):
        super(DroidBluetooth, self).__init__()
        self.droid = droid
        self.buffer = []
        self.connected = False
        self.socket = None

    def ensure_connected(self):
        if self.connected and self.socket:
            return True

        matches = bluetooth.find_service(uuid=self.service_uuid,
                                         address=self.bt_addr)
        if len(matches) == 0:
            log.warn("Couldn't find Android bluetooth server")
            return False

        match = matches[0]
        self.bt_host_port = (match['host'], match['port'])
        try:
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect(self.bt_host_port)
            self.socket.setblocking(0)
            self.connected = True
        except (socket.error, bluetooth.BluetoothError) as e:
            if self.socket:
                self.socket.close()
                self.socket = None

        return self.connected

    def loop(self):
        if not self.ensure_connected():
            log.warn('Failed to connect, will try again in %d seconds',
                     self.reconnect_timeout)
            gevent.sleep(self.reconnect_timeout)
            return

        lost_connection = False
        try:
            gevent.socket.wait_read(self.socket.fileno())
            data = self.socket.recv(1024)
            if len(data) == 0:
                lost_connection = True
        except (socket.timeout, socket.error) as e:
            lost_connection = True

        if lost_connection:
            log.warn('Bluetooth connection lost, will attempt to reconnect')
            self.connected = False
            self.gsocket.close()
            self.socket = self.gsocket = None
            return

        self.handle_data(data)

    def handle_data(self, data):
        self.buffer.extend(data)
        if len(self.buffer) < 6:
            return

        length, msg_type, checksum = struct.unpack('!BBL', ''.join(self.buffer[:6]))
        if len(self.buffer) < length + 6:
            return

        data = ''.join(self.buffer[6:length+6])
        self.buffer = self.buffer[length+6:]
        self.droid.handle_message(length, msg_type, checksum, data)

    def _run(self):
        while True:
            self.loop()

class Droid(object):
    msg_telemetry  = 100
    msg_photo_data = 101
    msg_types = ('Telemetry', 'PhotoData')

    def __init__(self, obc, photo_dir=None):
        self.obc = obc
        self.handlers = {
            self.msg_telemetry:  self.handle_telemetry,
            self.msg_photo_data: self.handle_photo_data
        }

        self.battery = self.radio = self.photo_count = 0
        self.latitude = self.longitude = self.altitude = 0
        self.droid_telemetry = None
        self.photo_data = []
        self.photo_index = 0
        self.photo_chunk = 0
        self._disconnected_nmea = None
        self.droid_bt = DroidBluetooth(self)
        self.droid_bt.start()

    def msg_type(self, msg_type_idx):
        return self.msg_types[msg_type_idx - 100]

    def handle_message(self, length, msg_type, checksum, data):
        handler = self.handlers.get(msg_type)
        if not handler:
            log.error('Unknown Droid message type: %d', msg_type)
            return

        if len(data) != length:
            log.error('Length mismatch for %s: Got %d expected %d',
                      self.msg_type(msg_type), len(data), length)
            return

        data_checksum = hab_utils.checksum(data)
        if data_checksum != checksum:
            log.error('Checksum mismatch for %s: Got 0x%02X expected 0x%02X',
                      self.msg_type(msg_type), data_checksum, checksum)
            return

        handler(data)

    def handle_telemetry(self, data):
        droid_data = data.split(',')
        self.battery = float(droid_data[0])
        self.radio = int(droid_data[1])
        self.photo_count = int(droid_data[2])
        self.latitude = float(droid_data[5])
        self.longitude = float(droid_data[6])
        self.altitude = float(droid_data[7])

        self.droid_telemetry = proto.DroidTelemetryMsg.from_data(
            battery=self.battery,
            radio=self.radio,
            photo_count=self.photo_count,
            latitude=self.latitude,
            longitude=self.longitude,
            altitude=self.altitude)

        #self.droid_telemetry = self.obc.build_nmea('D', data)

    def handle_photo_data(self, data):
        photo_index, photo_chunk, chunk_count, file_size = struct.unpack('!BHHL', data[:3])
        msg = proto.PhotoDataMsg.from_data(index=photo_index,
                                           chunk=photo_chunk,
                                           chunk_count=chunk_count,
                                           file_size=file_size)
        #self.photo_data.append(self.obc.build_nmea('DP',
        #    '%d,%d,%d,%s' % (photo_index, photo_chunk, chunk_count, data[3:])))

    @property
    def connected(self):
        return self.droid_bt.connected

    @property
    def disconnected_nmea(self):
        if not self._disconnected_nmea:
            self._disconnected_nmea = [self.obc.build_nmea('D', 'DISCONNECTED')]

        return self._disconnected_nmea

    @property
    def telemetry(self):
        if not self.droid_bt.connected:
            return self.disconnected_nmea

        t = []
        if self.droid_telemetry:
            t.append(self.droid_telemetry)
            self.droid_telemetry = None

        if len(self.photo_data) > 0:
            t.extend(self.photo_data)
            self.photo_data = []

        return t
