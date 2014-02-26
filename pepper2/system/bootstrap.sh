#!/bin/bash
#
# PEPPER-2 environment bootstrap script (called whenever pepper2 is started by the system)
#

set -e
system_dir=$(cd "`dirname "$0"`"; pwd)
pepper2_dir=$(dirname $system_dir)

cp $system_dir/upstart-pepper2.conf /etc/init/pepper2.conf

cd $pepper2_dir/temperature
echo 'Building temperature driver'
./waf configure build

cd $pepper2_dir/firmware
echo 'Installing firmware'
./install.sh
