#!/bin/bash

this_dir=$(cd "`dirname "$0"`"; pwd)

cd "$this_dir/ground"

./manage.py run_gunicorn 0.0.0.0:8000
