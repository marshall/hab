#!/usr/bin/env python
from gevent import monkey; monkey.patch_all()
import ground

import argparse
import os
import signal
import sys
import time

from ground import station

gs = None

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
    gs.join()

if __name__ == '__main__':
    main()
