#!/bin/bash
#
# Main PEPPER-2 entry point. Should be run as root (sudo)
#

hab_dir=$(cd "`dirname "$0"`"; pwd)
pepper2_dir=$hab_dir/pepper2

cd $pepper2_dir/temperature
./waf configure build

cd $pepper2_dir/firmware
./install.sh

cd $hab_dir
python -m pepper2.main $@
