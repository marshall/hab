import os
import sys

import appdirs

this_dir = os.path.abspath(os.path.dirname(__file__))
top_dir = os.path.join(this_dir, '..', '..')
sys.path.append(top_dir)

from pepper2 import log

app_dirs = appdirs.AppDirs('pepper2-gs', 'pepper2-gs')
if not os.path.exists(app_dirs.user_log_dir):
    os.makedirs(app_dirs.user_log_dir)

if not os.path.exists(app_dirs.user_data_dir):
    os.makedirs(app_dirs.user_data_dir)

photos_dir = os.path.join(app_dirs.user_data_dir, 'photos')
if not os.path.exists(photos_dir):
    os.makedirs(photos_dir)

log.setup(filename=os.path.join(app_dirs.user_log_dir, 'pepper2-gs.log'))
