#!/usr/bin/env python
from gevent import monkey; monkey.patch_all()
import ground

import argparse
import os
import signal
import sys
import time

import gevent.wsgi

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ground.settings')

from ground import station
from ground.wsgi import application
from django.utils.autoreload import code_changed, restart_with_reloader

RELOAD = False
gs = None

class Reload(gevent.GreenletExit):
    pass

def reload_watcher():
    global RELOAD
    while True:
        RELOAD = code_changed()
        if RELOAD:
            print '\n\nRELOAD\n\n'
            raise Reload()
        time.sleep(1)

def reloader(job):
    if not (isinstance(job.value, Reload) and RELOAD):
        return

    #wsgi_server.stop()
    #station.stop()
    gs.stop()
    gevent.sleep(0.5)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mock', default=False, action='store_true', help='Use mock data')
    parser.add_argument('--radio-port', default=None, help='Serial port for Radio')
    parser.add_argument('--radio-baud', default=9600, type=int, help='Serial baudrate for Radio')
    parser.add_argument('--gps-port', default=None, help='Serial port for GPS')
    parser.add_argument('--gps-baud', default=9600, type=int, help='Serial baudrate for GPS')
    parser.add_argument('--tcp', default=None, help='Connect to a TCP host[:port]. default port is 12345')
    parser.add_argument('--server', action='append')
    parser.add_argument('--auth-token', action='append')
    args = parser.parse_args()

    if not args.mock and args.radio_port is None and args.tcp is None:
        parser.error('Need at least one of --mock, --radio-port, or --tcp')

    global gs
    gs = station.GroundStation(mock=args.mock, radio_port=args.radio_port,
                               radio_baud=args.radio_baud, gps_port=args.gps_port,
                               gps_baud=args.gps_baud, tcp_addr=args.tcp,
                               servers=args.server, auth_tokens=args.auth_token)
    gs.start()

    job = gevent.spawn(reload_watcher)
    job.link(reloader)
    gs.join()
    #wsgi_server = gevent.wsgi.WSGIServer(('', 9909), application)
    #wsgi_server.serve_forever()

    if RELOAD:
        args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions] + sys.argv
        restart_with_reloader()

if __name__ == '__main__':
    main()
