#!/bin/bash

arduino_libs=$HOME/Documents/Arduino/libraries
this_dir=$(cd `dirname "$0"`; pwd)
lib_dir=$(cd "$this_dir/../lib"; pwd)

if [ ! -d $arduino_libs ]; then
    mkdir $arduino_libs
fi

for dir in `ls $lib_dir`; do
    full_dir=$lib_dir/$dir

    # check if symlink exists
    if [ -h $arduino_libs/$dir ]; then
        continue
    fi

    ln -s $full_dir $arduino_libs/$dir
done
