#!/usr/bin/env python
import argparse
import base64
import json
import os
import re
import sys

this_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(this_dir, '..'))

from pepper2 import proto

data = []
dataset = []

def scrape_line(line):
    global data
    global dataset

    if not line.startswith('['):
        data.append(dataset)
        dataset = []
        return

    pattern = r'\[(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d) ' \
              r'(?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d),(?P<millis>\d\d\d)\]' \
              r'\[(?P<logger>[^:]+):(?P<level>[^\]]+)\] (?P<message>.+)'

    m = re.match(pattern, line)
    if m.group('level') != 'DATA':
        return

    raw = base64.b64decode(m.group('message'))
    reader = proto.MsgReader()
    msg = reader.update(raw)

    if not msg:
        return

    time = int(m.group('hour')) * 60 * 60
    time += int(m.group('minute')) * 60
    time += int(m.group('second'))
    time += int(m.group('millis')) / 1000.0
    dataset.append(dict(time=time, msg=msg.as_dict()))

def print_stats():
    # In the final log file, the first dataset was from development, the second was
    # from a quick sanity test, and the third was the actual flight dataset
    print json.dumps(data[2])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    args = parser.parse_args()

    with open(args.file, 'r') as f:
        while True:
            line = f.readline()
            if not line:
                break
            scrape_line(line)

    print_stats()
if __name__ == '__main__':
    main()
