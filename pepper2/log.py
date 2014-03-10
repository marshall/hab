import base64
import json
import logging
import logging.handlers
import sys

DATA = 5
DEFAULT_FILENAME = '/var/log/pepper2.log'

class Pepper2Logger(logging.Logger):
    def __init__(self, name):
        super(Pepper2Logger, self).__init__(name)

    def message(self, msg):
        self.log(DATA, base64.b64encode(msg._buffer[:msg._buffer_len]))

def setup(filename=DEFAULT_FILENAME):
    logging.setLoggerClass(Pepper2Logger)
    logging.addLevelName(DATA, 'DATA')
    formatter = logging.Formatter(fmt='[%(asctime)s][%(name)s:%(levelname)s] %(message)s')

    root_logger = logging.getLogger()
    root_logger.setLevel(DATA)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    if filename:
        file_handler = logging.handlers.RotatingFileHandler(filename, maxBytes=10*1024*1024, backupCount=10)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(DATA)
        root_logger.addHandler(file_handler)
