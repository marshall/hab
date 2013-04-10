import BaseHTTPServer
import httplib
import multiprocessing
import os
import urllib
import Queue
import serial
import sys
import time

def read_serial(q):
    ser = serial.Serial(port='/dev/tty.usbserial-A601FDF6', baudrate=9600, timeout=1)
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

KML_TEMPLATE = '''
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
%(placemarks)s
</kml>
'''

PLACEMARK_TEMPLATE = '''
    <Placemark>
        <name>%(name)s</name>
        <Point>
            <coordinates>%(latitude)s,%(longitude)s,%(altitude)s</coordinates>
        </Point>
    </Placemark>
'''

class KmlServer(BaseHTTPServer.HTTPServer):
    def __init__(self, *args, **kwargs):
        BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
        self.queue = multiprocessing.Queue()
        self.serial_proc = multiprocessing.Process(target=read_serial, args=(self.queue,))
        self.serial_proc.start()
        self.placemarks = []

    def collect_queue(self):
        while True:
            try:
                self.handle_nmea(self.queue.get(False))
            except Queue.Queue.Empty:
                break

    def handle_nmea(self, nmea):
        args = nmea.strip().split(',')
        if args[0] == '$GPGGA':
            lat_n = float(args[2])/100.0
            long_e = float(args[4])/100.0
            altitude = float(args[9])

            self.placemarks.append({
                'name': args[1],
                'latitude': lat_n,
                'longitude': long_e,
                'altitude': altitude })

class KmlHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
        self.end_headers()
        self.server.collect_queue()
        for placemark in self.server.placemarks:
            self.wfile.write(PLACEMARK_TEMPLATE % placemark)

def main():
    httpd = KmlServer(('localhost', 9999), KmlHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()

if __name__ == '__main__':
    main()
