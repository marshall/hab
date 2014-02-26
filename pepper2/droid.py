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
        self.reader = proto.MsgReader()
        self.connected = False
        self.socket = None
        self.running = False

    def stop(self):
        self.running = False
        self.kill()

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
            log.info('Connecting to %s port %s..', *self.bt_host_port)
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect(self.bt_host_port)
            #self.socket.setblocking(0)
            self.socket_file = self.socket.makefile()
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
            msg = proto.MsgReader().read(self.socket_file)
            if not msg:
                lost_connection = True
        except (IOError, socket.timeout, socket.error) as e:
            lost_connection = True
        except (proto.BadMarker, proto.BadChecksum, proto.BadMsgType) as e:
            # these are "ok" -- logged upstream
            return

        if lost_connection:
            log.warn('Bluetooth connection lost, will attempt to reconnect')
            self.connected = False
            self.socket = self.socket_file = None
            self.reader.reset()
            return

        self.droid.handle_message(msg)

    def _run(self):
        self.running = True
        while self.running:
            self.loop()

class Droid(object):
    disconnected_msgs = [proto.DroidTelemetryMsg.from_data()]

    def __init__(self, obc, photo_dir=None):
        self.obc = obc
        self.handlers = {
            proto.DroidTelemetryMsg.TYPE: self.handle_telemetry,
            proto.PhotoDataMsg.TYPE     : self.handle_photo_data
        }

        self.battery = self.radio = self.photo_count = 0
        self.accel_state = self.accel_duration = 0
        self.latitude = self.longitude = 0
        self.droid_telemetry = None
        self.photo_data = []
        self.droid_bt = DroidBluetooth(self)
        self.droid_bt.start()

    def shutdown(self):
        self.droid_bt.stop()

    def handle_message(self, msg):
        handler = self.handlers.get(msg.msg_type)
        if not handler:
            log.error('Unknown Droid message type: %d', msg_type)
            return

        handler(msg)

    def handle_telemetry(self, msg):
        for name, defval in msg.data_attrs:
            setattr(self, name, getattr(msg, name))

        self.droid_telemetry = msg
        log.message(msg)

    def handle_photo_data(self, msg):
        '''self.photo_data.append(msg)'''
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

        '''if len(self.photo_data) > 0:
            t.extend(self.photo_data)
            self.photo_data = []'''

        return t
