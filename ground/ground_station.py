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
import gevent.socket as socket

from pynmea import nmea
from jinja2 import Environment, FileSystemLoader
import serial

this_dir = os.path.abspath(os.path.dirname(__file__))
beaglebone_dir = os.path.join(this_dir, '..', 'balloon', 'beaglebone')
sys.path.append(beaglebone_dir)

import hab_utils

logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                    level=logging.INFO)

@nmea.nmea_sentence
class PPR2T(nmea.NMEASentence):
    def __init__(self):
        param_map = (('Uptime', 'uptime'),
                     ('Mode', 'mode'),
                     ('CPU usage', 'cpu_usage'),
                     ('Free memory', 'free_mem'),
                     ('Temperature', 'temperature'),
                     ('Humidity', 'humidity'))
        super(PPR2T, self).__init__(param_map)

@nmea.nmea_sentence
class PPR2D(nmea.NMEASentence):
    def __init__(self):
        param_map = (('Battery', 'battery'),
                     ('Radio', 'radio'),
                     ('Photo count', 'photo_count'),
                     ('Latitude', 'latitude'),
                     ('Longitude', 'longitude'),
                     ('altitude', 'altitude'))
        super(PPR2D, self).__init__(param_map)

    @property
    def disconnected(self):
        return self.battery == 'DISCONNECTED'

@nmea.nmea_sentence
class PPR2DP(nmea.NMEASentence):
    def __init__(self):
        param_map = (('Photo index', 'photo_index'),
                     ('Photo chunk', 'photo_chunk'),
                     ('Chunk count', 'chunk_count'),
                     ('Data', 'data'))
        super(PPR2DP, self).__init__(param_map)

class GSWebapp(object):
    port = 9909
    def __init__(self, gs):
        self.gs = gs
        self.env = Environment(loader=FileSystemLoader(this_dir))

    def serve_forever(self):
        cherrypy.engine.autoreload.files.add(__file__)
        conf = {}
        for dirname in ('css', 'img', 'js', 'lib', 'fonts'):
            conf['/'+dirname] = {'tools.staticdir.on': True,
                                 'tools.staticdir.dir': os.path.join(this_dir, dirname)}

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
        if self.gs.telemetry:
            t = self.gs.telemetry
            data.update(uptime=int(t.uptime),
                        mode=t.mode,
                        cpu_usage=float(t.cpu_usage),
                        free_mem=float(t.free_mem),
                        temperature=float(t.temperature.replace('F', '')),
                        humidity=float(t.humidity))

        if self.gs.location:
            data.update(location=self.gs.location)

        if self.gs.droid_telemetry:
            dt = self.gs.droid_telemetry
            if dt.disconnected:
                data.update(droid=dict(connected=False))
            else:
                data.update(droid=dict(
                    connected=True,
                    battery=int(dt.battery),
                    radio=int(dt.radio),
                    photo_count=int(dt.photo_count),
                    latitude=float(dt.latitude),
                    longitude=float(dt.longitude),
                    altitude=float(dt.altitude)
                ))

        return json.dumps(data)

class GroundStation(object):
    def __init__(self, port):
        self.log = logging.getLogger('ground_station')

        if port == 'mock':
            gevent.spawn(self.mock_main_loop)
            return
        elif ':' in port:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host, port = port.split(':')
            self.socket.connect((host, port))
            self.stream = self.socket.makefile()
        else:
            self.stream = serial.Serial(port=port, baudrate=115200, timeout=1)
        self.location = None
        self.telemetry = None
        self.droid_telemetry = None
        self.photo_data = None
        self.init_photos_dir()
        gevent.spawn(self.main_loop)

    def init_photos_dir(self):
        home_dir = os.environ['HOME']
        pepper2_dir = os.path.join(home_dir, '.pepper2')
        self.photos_dir = os.path.join(pepper2_dir, 'photos')
        if not os.path.exists(self.photos_dir):
            os.makedirs(self.photos_dir)

    def maybe_save_chunk(self, chunk):
        photo_dir = os.path.join(self.photos_dir, str(chunk.photo_index))
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)

        chunk_file = os.path.join(photo_dir, '%s.chunk' % chunk.photo_chunk)
        if os.path.exists(chunk_file):
            chunk_checksum = int(chunk.checksum, 16)
            with open(chunk_file, 'r') as f:
                file_checksum = hab_utils.checksum(f.read())

            if chunk_checksum == file_checksum:
                return

        self.log.info('Saved photo %s chunk %s of %s to %s',
                      chunk.photo_index, chunk.photo_chunk, chunk.chunk_count,
                      chunk_file)

        with open(chunk_file, 'w') as f:
            f.write(chunk.data)

        self.photo_data = dict(photo_index=chunk.photo_index,
                               chunk_count=chunk.chunk_count,
                               missing=[])
        for c in range(0, chunk.chunk_count):
            if not os.path.exists(os.path.join(photo_dir, '%s.chunk' % str(c))):
                self.photo_data['missing'].append(c)

    def process_line(self, line):
        self.log.info(line)
        sentence = nmea.parse_sentence(line)

        if isinstance(sentence, nmea.GPGGA):
            self.location = hab_utils.gpgga_to_values(sentence)
        elif isinstance(sentence, PPR2T):
            self.telemetry = sentence
        elif isinstance(sentence, PPR2D):
            self.droid_telemetry = sentence
        elif isinstance(sentence, PPR2DP):
            self.maybe_save_chunk(sentence)

    def main_loop(self):
        self.log.info('started')
        try:
            while True:
                line = self.stream.readline()
                if line:
                    self.process_line(line.strip())
                gevent.sleep(0.25)
        except:
            self.log.exception('exception')
            pass

    def mock_main_loop(self):
        while True:
            gevent.sleep(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', help='Serial port to listen to')
    args = parser.parse_args()

    gs = GroundStation(args.port)
    webapp = GSWebapp(gs)
    webapp.serve_forever()

if __name__ == '__main__':
    main()
