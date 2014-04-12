#!/bin/bash

this_dir=$(cd "`dirname "$0"`"; pwd)

#RADIO_PORT=/dev/tty.usbmodem141351
RADIO_PORT=/dev/tty.usbmodem1411

#GPS_PORT=/dev/tty.usbmodem141361
GPS_PORT=/dev/tty.usbmodem1451

AUTH_TOKEN=59953bc90611f0540600fec4cd0af47ceea3ee59
#GSWEB_SERVER=home.hot-tea.org
GSWEB_SERVER=arcaner.xen.prgmr.com

$this_dir/ground/run_gs.py \
    --radio-port $RADIO_PORT \
    --gps-port $GPS_PORT \
    --server 127.0.0.1 \
    --auth-token $AUTH_TOKEN \
    --server $GSWEB_SERVER \
    --auth-token $AUTH_TOKEN
