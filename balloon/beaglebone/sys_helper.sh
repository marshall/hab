#!/bin/bash
#
# helper script for pepper2
#

this_dir=$(cd "`dirname "$0"`"; pwd)

set_hwclock() {
    new_time=$1
    /sbin/hwclock --set "--date=$new_time"
    /sbin/hwclock --hctosys
}

get_stats() {
    top -bn 1 | awk -f "$this_dir/sys_stats.awk"
}

usage() {
    echo "Usage: $0 <command> [args]"
    echo "Commands"
    echo "    get_stats"
    echo "    set_hwclock <date-time>"
    exit 1
}

if [[ "$1" = "" ]]; then
    usage
fi

case "$1" in
    get_stats)
        get_stats
        ;;

    set_hwclock)
        if [[ "$2" = "" ]]; then
            echo "No date specified"
            usage
        fi

        set_hwclock "$2"
        ;;

    *) echo "Unrecognized command: $1"
       usage
       ;;
esac
