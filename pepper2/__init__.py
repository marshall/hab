import logging
import os

this_dir = os.path.abspath(os.path.dirname(__file__))

logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                    level=logging.INFO)
