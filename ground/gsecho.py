#!/usr/bin/env python
import argparse
import json
import logging
import os
import sys

this_dir = os.path.abspath(os.path.dirname(__file__))
top_dir = os.path.join(this_dir, '..')
sys.path.append(top_dir)

import gevent
import pepper2.log
from pepper2 import proto, radio
import serial

pepper2.log.setup(None)
log = logging.getLogger('gsecho')

def echo_msg(msg):
    log.info('%s %s', msg.__class__.__name__, msg.as_dict())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port')
    parser.add_argument('baud')
    args = parser.parse_args()
    gs_radio = radio.Radio(handler=echo_msg, port=args.port, baud=args.baud, uart=None)

    while True:
        gevent.sleep(1)

if __name__ ==  '__main__':
    main()
