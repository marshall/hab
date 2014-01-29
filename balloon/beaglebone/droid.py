import logging
import socket
import struct
import threading
import time

import bluetooth
from pynmea import nmea, utils

log = logging.getLogger('droid')

class DroidBluetooth(threading.Thread):
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
            self.socket.settimeout(self.socket_timeout)
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
            time.sleep(self.reconnect_timeout)
            return

        lost_connection = False
        try:
            data = self.socket.recv(1024)
            if len(data) == 0:
                lost_connection = True
        except socket.timeout, e:
            lost_connection = True

        if lost_connection:
            log.warn('Bluetooth connection lost, will attempt to reconnect')
            self.connected = False
            self.socket.close()
            self.socket = None
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

    def run(self):
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
        self.telemetry_lock = threading.Lock()
        self._disconnected_nmea = None
        self.droid_bt = DroidBluetooth(self)
        self.droid_bt.start()

    def msg_type(self, msg_type_idx):
        return self.msg_types[msg_type_idx - 100]

    def checksum(self, data):
        ck = 0
        for ch in data:
            ck ^= ord(ch)
        return ck

    def handle_message(self, length, msg_type, checksum, data):
        handler = self.handlers.get(msg_type)
        if not handler:
            log.error('Unknown Droid message type: %d', msg_type)
            return

        if len(data) != length:
            log.error('Length mismatch for %s: Got %d expected %d',
                      self.msg_type(msg_type), len(data), length)
            return

        data_checksum = self.checksum(data)
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

        with self.telemetry_lock:
            self.droid_telemetry = self.obc.build_nmea('D', data)

    def handle_photo_data(self, data):
        photo_index, photo_chunk = struct.unpack('!BB', data[:2])
        with self.telemetry_lock:
            self.photo_data.append(self.obc.build_nmea('DP',
                '%d,%d,%s' % (photo_index, photo_chunk, data[2:])))

    @property
    def connected(self):
        return self.droid_bt.connected

    @property
    def disconnected_nmea(self):
        if not self._disconnected_nmea:
            self._disconnected_nmea = self.obc.build_nmea('D', 'DISCONNECTED')

        return self._disconnected_nmea

    @property
    def telemetry(self):
        if not self.droid_bt.connected:
            return [self.disconnected_nmea]

        t = []
        with self.telemetry_lock:
            if self.droid_telemetry:
                t.append(self.droid_telemetry)
                self.droid_telemetry = None

            if len(self.photo_data) > 0:
                t.extend(self.photo_data)
                self.photo_data = []

        return t
