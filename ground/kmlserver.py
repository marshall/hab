import BaseHTTPServer
import httplib
import multiprocessing
import os
import urllib
import Queue
import serial
import sys
import time

def read_serial_real(q):
    ser = serial.Serial(port='/dev/tty.usbserial-A601FDF6',
                        baudrate=9600,
                        timeout=1)
    try:
        while True:
            line = ser.readline()
            if not line:
                continue

            print line
            q.put_nowait(line)
    except:
        pass

    ser.close()

fake_data = open('data/cubesat.nmea', 'r').read().splitlines()

def read_serial_fake(q):
    i = 0
    while True:
        print fake_data[i]
        q.put_nowait(fake_data[i])
        if i == len(fake_data) - 1:
            i = 0
        else:
            i += 1
        time.sleep(1)

read_serial = read_serial_fake

KML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="transBluePoly">
      <LineStyle>
        <color>7f00ffff</color>
        <width>4</width>
      </LineStyle>
      <PolyStyle>
        <color>7dff0000</color>
      </PolyStyle>
    </Style>
    <Placemark>
      <name>PEPPER-1 Flight Path</name>
      <styleUrl>#transBluePoly</styleUrl>
      <visibility>1</visibility>
      <LookAt>
        <longitude>%(first_lng)f</longitude>
        <latitude>%(first_lat)f</latitude>
        <altitude>%(max_alt).2f</altitude>
        <tilt>44</tilt>
        <range>500</range>
      </LookAt>
      <LineString>
        <extrude>1</extrude>
        <tesselate>1</tesselate>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
          %(coords)s
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
'''

COORDS_TEMPLATE = '%(longitude)f,%(latitude)f,%(altitude)s'

class KmlServer(BaseHTTPServer.HTTPServer):
    def __init__(self, *args, **kwargs):
        BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
        self.queue = multiprocessing.Queue()
        self.serial_proc = multiprocessing.Process(target=read_serial, args=(self.queue,))
        self.serial_proc.start()
        self.coords = []

    def collect_queue(self):
        while True:
            try:
                self.handle_nmea(self.queue.get(False))
            except Queue.Empty:
                break

    def handle_nmea(self, nmea):
        def lat2dec(lat, dir):
            d = float(lat[0:2]) + (float(lat[2:]) / 60)
            if dir == 'S':
              d *= -1
            return d

        def lng2dec(lng, dir):
            d = float(lng[0:3]) + (float(lng[3:]) / 60)
            if dir == 'W':
                d *= -1
            return d

        args = nmea.strip().split(',')
        if args[0] == '$GPGGA':
            self.coords.append(dict(
                latitude=lat2dec(args[2], args[3]),
                longitude=lng2dec(args[4], args[5]),
                altitude= float(args[9]) if args[9] else 650
            ))
        elif args[0] == '$GPRMC':
            self.coords.append(dict(
              latitude=lat2dec(args[3], args[4]),
              longitude=lng2dec(args[5], args[6]),
              altitude=650,
            ))

class KmlHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    server_version = 'KmlServer/0.1'

    def do_GET(self):
        self.server.collect_queue()

        coords_out = ' \n'.join([COORDS_TEMPLATE % c for c in self.server.coords])

        kml = KML_TEMPLATE % {'coords': coords_out,
            'first_lat': self.server.coords[0]['latitude'],
            'first_lng': self.server.coords[0]['longitude'],
            'max_alt': 1000
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.google-earth.kml+xml')
        self.send_header('Content-Length', str(len(kml)))
        self.end_headers()
        self.wfile.write(kml)

def main():
    httpd = KmlServer(('localhost', 9999), KmlHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()

if __name__ == '__main__':
    main()
