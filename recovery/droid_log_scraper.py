#!/usr/bin/env python
import argparse
import json

telemetry = []
def scrape_line(line):
    data = json.loads(line)
    if data['type'] == 'telemetry':
        telemetry.append(data['data'])

def print_stats():
    print json.dumps(telemetry)

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
