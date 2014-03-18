import logging
import socket
import struct
import time

import bluetooth
import gevent
import gevent.queue
from pynmea import nmea, utils

import hab_utils
import proto
import worker

class DroidBluetooth(object):
    daemon            = True
    bt_addr           = '0C:DF:A4:B1:D7:7A'
    service_uuid      = 'de746609-6dbf-4917-9040-40d1d2ce9c79'
    socket_timeout    = 60
    reconnect_timeout = 15

    def __init__(self, droid):
        super(DroidBluetooth, self).__init__()
        self.log = logging.getLogger('droid')
        self.droid = droid
        self.buffer = []
        self.jobs = []
        self.connected = False
        self.socket = None
        self.running = False
        self.write_queue = gevent.queue.Queue()

    def start(self):
        self.running = True
        self.jobs = [gevent.spawn(lambda: self.loop(self.reader)),
                     gevent.spawn(lambda: self.loop(self.writer))]

    def stop(self):
        self.running = False
        for job in self.jobs:
            job.kill()

    def send_message(self, msg):
        self.write_queue.put(msg)

    def ensure_connected(self):
        if self.connected and self.socket:
            return True

        matches = bluetooth.find_service(uuid=self.service_uuid,
                                         address=self.bt_addr)
        if len(matches) == 0:
            self.log.warn("Couldn't find Android bluetooth server")
            return False

        match = matches[0]
        self.bt_host_port = (match['host'], match['port'])
        try:
            self.log.info('Connecting to %s port %s..', *self.bt_host_port)
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect(self.bt_host_port)
            self.socket_file = self.socket.makefile()
            self.connected = True
        except (socket.error, bluetooth.BluetoothError) as e:
            if self.socket:
                self.socket.close()
                self.socket = None

        return self.connected

    def reader(self):
        try:
            gevent.socket.wait_read(self.socket.fileno())
            msg = proto.MsgReader().read(self.socket_file)
            if not msg:
                return False
        except (proto.BadMarker, proto.BadChecksum, proto.BadMsgType) as e:
            # these are logged upstream
            return False

        self.droid.handle_message(msg)
        return True

    def writer(self):
        msg = self.write_queue.get()
        gevent.socket.wait_write(self.socket.fileno())
        self.socket.sendall(msg)
        return True

    def loop(self, worker):
        while self.running:
            if not self.ensure_connected():
                self.log.warn('Failed to connect, will try again in %d seconds',
                              self.reconnect_timeout)
                gevent.sleep(self.reconnect_timeout)
                continue

            lost_connection = False
            try:
                lost_connection = not worker()
            except (IOError, socket.timeout, socket.error) as e:
                lost_connection = True

            if lost_connection:
                self.log.warn('Bluetooth connection lost, will attempt to reconnect')
                self.connected = False
                self.socket = self.socket_file = None

class Droid(object):
    disconnected_msgs = [proto.DroidTelemetryMsg.from_data()]

    def __init__(self, obc, photo_dir=None):
        self.obc = obc
        self.handlers = {
            proto.DroidTelemetryMsg.TYPE: self.handle_telemetry,
            proto.PhotoDataMsg.TYPE     : self.handle_photo_data
        }

        self.log = logging.getLogger('droid')
        self.battery = self.radio = self.photo_count = 0
        self.radio_dbm = self.radio_bars = 0
        self.accel_state = self.accel_duration = 0
        self.latitude = self.longitude = 0
        self.droid_telemetry = None
        self.photo_data = []
        self.droid_bt = DroidBluetooth(self)

    def start(self):
        self.droid_bt.start()

    def stop(self):
        self.droid_bt.stop()

    def send_message(self, msg):
        self.droid_bt.send_message(msg)

    def handle_message(self, msg):
        handler = self.handlers.get(msg.msg_type)
        if not handler:
            self.log.error('Unknown Droid message type: %d', msg_type)
            return

        handler(msg)

    def handle_telemetry(self, msg):
        for name, defval in msg.data_attrs:
            setattr(self, name, getattr(msg, name))

        self.droid_telemetry = msg
        self.log.message(msg)

    def handle_photo_data(self, msg):
        #self.log.info('index=%d, chunk=%d, chunk_count=%d, file_size=%d',
        #              msg.index, msg.chunk, msg.chunk_count, msg.file_size)

        self.obc.send_message(msg, src='droid')

    @property
    def connected(self):
        return self.droid_bt.connected

    @property
    def telemetry(self):
        if not self.droid_bt.connected:
            return self.disconnected_msgs

        t = []
        if self.droid_telemetry:
            t.append(self.droid_telemetry)
            self.droid_telemetry = None

        return t
