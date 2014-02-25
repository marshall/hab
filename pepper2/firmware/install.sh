#!/bin/bash

set -e
dtc -O dtb -o BB-W1-00A0.dtbo -b 0 -@ BB-W1-00A0.dts
sudo cp BB-W1-00A0.dtbo /lib/firmware/
sudo sh -c 'echo BB-W1:00A0 > /sys/devices/bone_capemgr.9/slots'
