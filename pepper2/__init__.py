import logging
import os

import main

from worker import Worker

try:
    import droid
    import obc
except ImportError, e:
    # This is only here for the ground station..
    pass
