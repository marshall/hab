#!/usr/bin/env python
import argparse
import logging
import json
import os
import sys

import cherrypy
from cherrypy.lib.static import serve_file
import gevent
import gevent.wsgi
import gevent.server
import gevent.socket as socket

from pynmea import nmea
from jinja2 import Environment, FileSystemLoader
import serial

this_dir = os.path.abspath(os.path.dirname(__file__))
top_dir = os.path.join(this_dir, '..')
sys.path.append(top_dir)

from pepper2 import hab_utils, proto

logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                    level=logging.INFO)

home_dir = os.environ['HOME']
pepper2_dir = os.path.join(home_dir, '.pepper2')
photos_dir = os.path.join(pepper2_dir, 'photos')
if not os.path.exists(photos_dir):
    os.makedirs(photos_dir)

class GSWebapp(object):
    port = 9909
    def __init__(self, gs):
        self.gs = gs
        self.env = Environment(loader=FileSystemLoader(this_dir))
        self.log = logging.getLogger('gsweb')

    def serve_forever(self):
        cherrypy.engine.autoreload.files.add(__file__)
        conf = {}

        for dirname in ('css', 'img', 'js', 'lib', 'fonts'):
            conf['/'+dirname] = {'tools.staticdir.on': True,
                                 'tools.staticdir.dir': os.path.join(this_dir, dirname)}

        global photos_dir
        conf['/photos'] = {'tools.staticdir.on': True,
                           'tools.staticdir.dir': photos_dir}
        app = cherrypy.tree.mount(self, '/', config=conf)
        gevent.wsgi.WSGIServer(('', self.port), app).serve_forever()

    @cherrypy.expose
    def index(self):
        tmpl = self.env.get_template('ground_station.html')
        return tmpl.render(gs=self.gs)

    @cherrypy.expose
    def api(self):
        cherrypy.response.headers['Content-Type'] = 'application/json'

        data = dict()
        if self.gs.mock:
            data.update(mock=True)

        if self.gs.telemetry:
            t = self.gs.telemetry
            data.update(uptime=t.uptime,
                        mode=t.modes[t.mode],
                        cpu_usage=t.cpu_usage,
                        free_mem=t.free_mem,
                        int_temperature=t.int_temperature,
                        int_humidity=t.int_humidity,
                        ext_temperature=t.ext_temperature)

        if self.gs.location:
            l = self.gs.location
            data.update(location=dict(latitude=l.latitude,
                                      longitude=l.longitude,
                                      altitude=l.altitude,
                                      quality=l.quality,
                                      satellites=l.satellites,
                                      speed=l.speed))

        if self.gs.droid_telemetry:
            dt = self.gs.droid_telemetry
            if dt.battery == 0 and dt.radio == 0:
                data.update(droid=dict(connected=False))
            else:
                data.update(droid=dict(
                    connected=True,
                    battery=int(dt.battery),
                    radio=int(dt.radio),
                    accel_state=dt.accel_states[dt.accel_state],
                    accel_duration=dt.accel_duration,
                    photo_count=int(dt.photo_count),
                    latitude=float(dt.latitude),
                    longitude=float(dt.longitude)
                ))

        data.update(photo_status=[])
        status_attrs = ('index', 'chunks', 'downloading', 'missing', 'url')
        for status in self.gs.photo_status:
            photo_status = {}
            for attr in status_attrs:
                photo_status[attr] = getattr(status, attr)
            data['photo_status'].append(photo_status)

        return json.dumps(data)

class PhotoData(object):
    def __init__(self, data):
        self.log = logging.getLogger('photo_data')
        self.index = data.index
        self.chunks = data.chunk_count
        self.downloading = True
        self.missing = range(0, data.chunk_count)
        self.url = None

    def get_photo_dir(self):
        global photos_dir
        photo_dir = os.path.join(photos_dir, '%03d' % self.index)
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)
        return photo_dir

    def get_chunk_file(self, chunk_index):
        return os.path.join(self.get_photo_dir(), '%03d.chunk' % chunk_index)

    def save_chunk(self, chunk):
        chunk_file = self.get_chunk_file(chunk.chunk)
        with open(chunk_file, 'w') as f:
            f.write(chunk.photo_data)

        self.log.info('Saved photo %s chunk %s of %s to %s',
                      chunk.index, chunk.chunk, chunk.chunk_count,
                      chunk_file)

        if chunk.chunk in self.missing:
            self.missing.remove(chunk.chunk)

        if len(self.missing) == 0:
            self.build_photo()

    def build_photo(self):
        global photos_dir
        photo_path = os.path.join(photos_dir, '%03d.jpg' % self.index)
        with open(photo_path, 'w') as photo_file:
            for c in range(0, self.chunks):
                photo_file.write(open(self.get_chunk_file(c), 'r').read())

        self.downloading = False
        self.url = '/photos/%03d.jpg' % self.index

class GroundStation(object):
    bind_port = 9910

    def __init__(self, mock=False, serial_port=None, serial_baud=9600,
                 tcp_addr=None, forward_addr=None, listen=False):
        self.log = logging.getLogger('ground_station')
        self.reader = proto.MsgReader()
        self.mock = mock
        self.forward_addr = forward_addr
        self.forward_socket = None
        self.location = None
        self.telemetry = None
        self.droid_telemetry = None
        self.photo_status = []

        job = self.main_loop
        if mock:
            job = self.mock_main_loop
        elif tcp_addr:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(self.to_addr(tcp_addr, 12345))
            self.stream = self.socket.makefile()
        elif serial_port:
            self.stream = serial.Serial(port=serial_port, baudrate=serial_baud, timeout=1)
            job = self.main_loop
        elif listen:
            self.server = gevent.server.StreamServer(('0.0.0.0', self.bind_port), self.handle_client)
            job = self.server.serve_forever

        gevent.spawn(job)

    def to_addr(self, host, default_port):
        port = default_port
        if ':' in host:
            host, port = host.split(':')
        return (host, port)

    def get_photo_status(self, photo):
        status = filter(lambda s: s.index == photo.index, self.photo_status)
        if len(status) > 0:
            return status[0]

        status = PhotoData(photo)
        self.photo_status.append(status)
        return status

    def maybe_save_chunk(self, chunk):
        status = self.get_photo_status(chunk)
        status.save_chunk(chunk)

    def forward_message(self, msg):
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
                self.forward_socket = None

    def process_message(self, msg):
        if self.forward_addr:
            gevent.spawn(lambda: self.forward_message(msg))

        if isinstance(msg, proto.LocationMsg):
            self.location = msg
        elif isinstance(msg, proto.TelemetryMsg):
            self.telemetry = msg
        elif isinstance(msg, proto.DroidTelemetryMsg):
            self.droid_telemetry = msg
        elif isinstance(msg, proto.PhotoDataMsg):
            self.maybe_save_chunk(msg)

    def handle_client(self, socket, addr):
        self.log.info('New connection from %s:%s', *addr)
        self.socket = socket
        self.stream = socket.makefile()
        self.main_loop()

    def main_loop(self):
        try:
            while True:
                try:
                    reader = proto.MsgReader()
                    msg = reader.read(self.stream)
                    if msg:
                        self.process_message(msg)
                except (proto.BadMarker, proto.BadChecksum, proto.BadMsgType) as e:
                    pass

                gevent.sleep(0.1)
        except:
            self.log.exception('exception')
            pass

    def mock_main_loop(self):
        self.mock = True
        while True:
            gevent.sleep(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mock', default=False, action='store_true', help='Use mock data')
    parser.add_argument('--port', default=None, help='Serial port to listen to')
    parser.add_argument('--baud', default=9600, type=int, help='Serial port baudrate')
    parser.add_argument('--tcp', default=None, help='Connect to a TCP host[:port]. default port is 12345')
    parser.add_argument('--forward-addr', default=None, help='Forward messages to TCP host[:port]. default port is 9910')
    parser.add_argument('--listen', default=False, action='store_true', help='Listen on 0.0.0.0:9910 for incoming messages')

    args = parser.parse_args()

    print 'Create GS'
    gs = GroundStation(mock=args.mock, serial_port=args.port,
                       serial_baud=args.baud, tcp_addr=args.tcp,
                       forward_addr=args.forward_addr, listen=args.listen)

    print 'Create webapp'
    webapp = GSWebapp(gs)
    print 'Serve webapp forever'
    webapp.serve_forever()

if __name__ == '__main__':
    main()
