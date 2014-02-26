#!/bin/bash

set -e

echo 'Compiling DTS'
dtc -O dtb -o BB-W1-00A0.dtbo -b 0 -@ BB-W1-00A0.dts

echo 'Copying DTBOs'
sudo cp BB-W1-00A0.dtbo /lib/firmware/

echo 'Enabling firmware'
sudo sh -c 'echo BB-W1:00A0 > /sys/devices/bone_capemgr.9/slots' || echo -n ''
