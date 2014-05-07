#!/bin/bash
FFMPEG=/usr/local/Cellar/ffmpeg/2.2.1/bin/ffmpeg
$FFMPEG -framerate 8 \
       -start_number 0 \
       -i data/stats_frames/%05d.png \
       -c:v libx264 \
       -pix_fmt yuv420p \
       data/stats.mp4
