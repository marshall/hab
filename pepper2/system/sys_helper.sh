#!/bin/bash
#
# helper script for pepper2
#

this_dir=$(cd "`dirname "$0"`"; pwd)

set_time() {
    new_date=$1
    new_time=$2

    date "+%Y-%m-%d %T" --utc --set="$new_date $new_time"
    /sbin/hwclock --systohc
    /sbin/hwclock --utc
}

get_stats() {
    top -bn 1 | awk -f "$this_dir/sys_stats.awk"
}

usage() {
    echo "Usage: $0 <command> [args]"
    echo "Commands"
    echo "    get_stats"
    echo "    set_time <YYYY-MM-DD> <HH:mm:ss>"
    exit 1
}

if [[ "$1" = "" ]]; then
    usage
fi

case "$1" in
    get_stats)
        get_stats
        ;;

    set_time)
        if [[ "$2" = "" ]]; then
            echo "No date specified"
            usage
        elif [[ "$3" = "" ]]; then
            echo "No time specified"
            usage
        fi

        set_time "$2" "$3"
        ;;

    *) echo "Unrecognized command: $1"
       usage
       ;;
esac
