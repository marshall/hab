#!/bin/bash

this_dir=$(cd "`dirname "$0"`"; pwd)
ground_dir=$this_dir/ground

cat <<THIS | sqlite3 $ground_dir/db.sqlite3
delete from api_photodata;
delete from api_photostatus;
THIS

uname=$(uname)
if [ "$uname" = "Darwin" ]; then
    gs_data_dir="$HOME/Library/Application Support/pepper2-gs"
elif [ "$uname" = "Linux" ]; then
    gs_data_dir=$HOME/.config/pepper2-gs
fi

rm -rf "$gs_data_dir/photos"
