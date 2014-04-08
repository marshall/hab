#!/usr/bin/env python
from gevent import monkey; monkey.patch_all()
import base64
import datetime
import httplib
import json
import logging
import os
import sys
import time
import urllib2

import gevent
import gevent.server
import gevent.socket as socket
import serial

this_dir = os.path.abspath(os.path.dirname(__file__))
top_dir = os.path.join(this_dir, '..', '..')
sys.path.append(top_dir)

from pepper2 import gps, hab_utils, proto, radio

from . import app_dirs

class GSWebClient(object):
    def __init__(self, addr, auth_token):
        self.addr = addr
        self.auth_token = auth_token
        self.headers={ 'Authorization': 'Token %s' % auth_token }
        self.log = logging.getLogger('gswebclient')
        self.completed_photos = []
        self.error_count = 0

    def complete_photo(self, index):
        self.completed_photos.append(index)

    def is_photo_complete(self, index):
        return index in self.completed_photos

    def post(self, uri, callback=None, **data):
        def post_job():
            try:
                raw_data = json.dumps(data)
                self.log.info('POST %s: %s', uri, raw_data)
                headers = self.headers.copy()

                headers['Content-Length'] = len(raw_data)
                headers['Content-Type'] = 'application/json'

                conn = httplib.HTTPConnection(self.addr)
                conn.request('POST', uri, raw_data, headers)
                response = conn.getresponse()
                if response.status != 200:
                    self.log.warning('%d %s', response.status, response.reason)
                    self.log.warning(response.read())
                    self.error_count += 1
                    return

                self.error_count = 0
                if callback:
                    callback(json.load(response))
            except:
                self.log.warning('Failed to POST to %s%s', self.addr, uri)
                self.error_count += 1

        gevent.spawn(post_job)

    def post_photo_data(self, photo_data):
        def data_posted(result):
            if result is not None and result['complete']:
                self.complete_photo(photo_data.index)

        self.post('/api/photos/', index=photo_data.index,
                                  chunks=photo_data.chunk_count,
                                  chunk=photo_data.chunk,
                                  data=base64.b64encode(photo_data.photo_data),
                                  callback=data_posted)

    def is_active(self):
        return self.error_count < 5

class GroundStation(object):
    bind_port = 9910
    location_save_interval = 30

    def __init__(self, mock=False, radio_port=None, radio_baud=9600,
                 gps_port=None, gps_baud=9600, tcp_addr=None,
                 servers=None, auth_tokens=None):
        self.log = logging.getLogger('ground_station')
        self.mock = mock
        self.servers = servers
        self.forward_socket = None
        self.location = None
        self.telemetry = None
        self.droid_telemetry = None
        self.radio = None
        self.gps = None
        self.stats = dict(location={}, droid={})
        self.last_self_location_time = 0
        self.last_balloon_location_time = 0
        self.last_downloaded_photo = 0
        self.mock_job = None
        self.web_clients = []
        self.requested_next = []
        self.jobs = []

        if servers and auth_tokens:
            if len(servers) != len(auth_tokens):
                raise ValueError('Length of servers != Length of auth tokens')

            for i in range(0, len(servers)):
                self.web_clients.append(GSWebClient('%s:8000' % servers[i], auth_tokens[i]))

        if radio_port:
            self.radio = radio.Radio(handler=self.handle_msg, port=radio_port,
                                     baud=radio_baud, uart=None, power_level=2)
        elif tcp_addr:
            self.radio = radio.TCPRadio(handler=self.handle_msg, host=tcp_addr)

        if gps_port:
            self.gps = gps.GPS(port=gps_port, baud=gps_baud, uart=None, handler=self.save_self_location)

        '''elif listen:
            self.radio = radio.TCPServerRadio(handler=self.handle_msg)'''

    def start(self):
        if self.mock:
            self.jobs.append(gevent.spawn(self.mock_main_loop))
            return

        if self.radio is not None:
            self.jobs.append(self.radio)
            self.radio.start()

        if self.gps is not None:
            self.jobs.append(self.gps)
            self.gps.start()

    def stop(self):
        for job in self.jobs:
            job.kill()
            job.join()

    def join(self):
        for job in self.jobs:
            job.join()

    def to_addr(self, host, default_port):
        port = default_port
        if ':' in host:
            host, port = host.split(':')
        return (host, port)

    def get_photo_status(self, photo):
        return status

    '''def forward_message(self, msg):
        try:
            if not self.forward_socket:
                self.forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.forward_socket.connect(self.to_addr(self.forward_addr, self.bind_port))

            self.forward_socket.send(msg.as_buffer())
        except socket.error, e:
            try:
                if self.forward_socket:
                    self.forward_socket.close()
            except:
                pass
            finally:
                self.forward_socket = None'''

    def post_location(self, location, type='B'):
        for client in self.web_clients:
            client.post('/api/locations/', latitude=location.latitude,
                                           longitude=location.longitude,
                                           altitude=location.altitude,
                                           type=type)

    def post_stats(self):
        for client in self.web_clients:
            client.post('/api/stats/', **self.stats)

    def save_self_location(self, gps):
        if gps.longitude == 0 or gps.latitude == 0:
            return

        if time.time() - self.last_self_location_time >= self.location_save_interval:
            self.post_location(gps, type='C')
            self.last_self_location_time = time.time()

    def save_balloon_location(self, location):
        if not location:
            return

        self.location = location
        self.stats['location'].update(**location.as_dict())
        self.post_stats()

        if time.time() - self.last_balloon_location_time >= self.location_save_interval:
            self.post_location(location, type='B')
            self.last_balloon_location_time = time.time()

    def save_telemetry(self, telemetry):
        self.telemetry = telemetry
        telemetry_stats = telemetry.as_dict()
        telemetry_stats['mode'] = telemetry.modes[telemetry.mode]
        self.stats.update(**telemetry_stats)
        self.post_stats()

    def save_droid_telemetry(self, droid_telemetry):
        self.droid_telemetry = droid_telemetry

        droid_stats = self.stats['droid']
        if droid_telemetry.battery == 0 and droid_telemetry.radio_dbm == 0:
            droid_stats.update(connected=False)
            return

        droid_stats.update(connected=True, **droid_telemetry.as_dict())
        self.post_stats()

    def save_photo_data(self, photo_data):
        all_posted = []
        for client in self.web_clients:
            if client.is_photo_complete(photo_data.index):
                continue

            client.post_photo_data(photo_data)

        #if all((c.is_photo_complete(photo_data.index) or not c.is_active() for c in self.web_clients)):
        #    self.start_next_photo(photo_data.index)

    def start_next_photo(self, index):
        if not self.droid_telemetry:
            return

        next_index = self.droid_telemetry.photo_count - 1
        if index < next_index and next_index not in self.requested_next:
            self.radio.write(proto.StartPhotoDataMsg.from_data(index=index))
            self.requested_next.append(next_index)

    def handle_msg(self, msg):
        '''if self.forward_addr:
            gevent.spawn(lambda: self.forward_message(msg))'''

        if isinstance(msg, proto.LocationMsg):
            self.save_balloon_location(msg)
        elif isinstance(msg, proto.TelemetryMsg):
            self.save_telemetry(msg)
        elif isinstance(msg, proto.DroidTelemetryMsg):
            self.save_droid_telemetry(msg)
        elif isinstance(msg, proto.PhotoDataMsg):
            self.save_photo_data(msg)

        self.log.message(msg)

    def mock_main_loop(self):
        self.mock = True
        while True:
            gevent.sleep(1)
