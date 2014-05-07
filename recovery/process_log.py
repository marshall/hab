#!/usr/bin/env python
from datetime import datetime, timedelta
import json
import math
import os
import sys

# TODO narrow in on start time
start = datetime(2014, 4, 12, 11, 29)

BASE_KML = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>
        <name>PEPPER-2 Flight Path</name>
        <Style id="yellowPoly">
            <LineStyle>
                <color>7f00ffff</color>
                <width>4</width>
            </LineStyle>
            <PolyStyle>
                <color>7f00ff00</color>
            </PolyStyle>
        </Style>
        <Placemark>
            <name>Flight path</name>
            <description>
                {flight_time_hr:0.2f} hours, Ascent @ {ascent_ms:0.1f} m/s, Descent @ {descent_ms:0.1f} m/s
            </description>
            <styleUrl>#yellowPoly</styleUrl>
            <LineString>
                <extrude>1</extrude>
                <tesselate>1</tesselate>
                <altitudeMode>absolute</altitudeMode>
                <coordinates>
                    {flight_path}
                </coordinates>
            </LineString>
        </Placemark>
        <Placemark>
            <name>Balloon Launch</name>
            <description>{launch.date:%m/%d/%Y %H:%M:%S}</description>
            <Point><coordinates>{launch.longitude},{launch.latitude},{launch.altitude_m}</coordinates></Point>
        </Placemark>
        <Placemark>
            <name>Balloon Burst</name>
            <description>{burst.date:%m/%d/%Y %H:%M:%S}, Altitude {burst.altitude:0.2f} km</description>
            <Point><coordinates>{burst.longitude},{burst.latitude},{burst.altitude_m}</coordinates></Point>
        </Placemark>
        <Placemark>
            <name>Balloon Landing</name>
            <description>{landing.date:%m/%d/%Y %H:%M:%S}</description>
            <Point><coordinates>{landing.longitude},{landing.latitude},{landing.altitude_m}</coordinates></Point>
        </Placemark>
    </Document>
</kml>'''

FLIGHT_PATH = '{point.longitude},{point.latitude},{point.altitude_m}\n'
class Point(object):
    def __init__(self, entry):
        self.latitude = entry['msg']['latitude']
        self.longitude = entry['msg']['longitude']
        self.altitude = entry['msg']['altitude']
        self.altitude_m = self.altitude * 1000
        self.date = start + timedelta(seconds=entry['time'])

sensors = dict(ext_temperature={'min': 0, 'max': 0},
               int_temperature={'min': 0, 'max': 0},
               int_humidity={'min': 0, 'max': 0})

ground_speed_kmh = {'max': 0, 'min': 0, 'avg': 0}

def calc_min_max(msg):
    global sensors
    if 'int_temperature' in msg and msg['int_temperature'] > 40:
        return

    for key in sensors.keys():
        if key in msg:
            sensors[key]['min'] = min(sensors[key]['min'], msg[key])
            sensors[key]['max'] = max(sensors[key]['max'], msg[key])

def calc_ground_speed(point1, point2):
    km = haversine_distance(point1.latitude, point1.longitude,
                            point2.latitude, point2.longitude)

    time = (point2.date - point1.date).total_seconds()

    kmh = km / (time / 3600.0)
    ground_speed_kmh['min'] = min(kmh, ground_speed_kmh['min'])
    ground_speed_kmh['max'] = max(kmh, ground_speed_kmh['max'])

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371 #km
    dLat = math.radians(lat2-lat1)
    dLon = math.radians(lon2-lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.sin(dLon/2) * math.sin(dLon/2) * math.cos(lat1) * math.cos(lat2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = R * c
    return d

def main():
    log = json.load(open('data/obc_log.json'))
    flight_path = ''
    launch = None
    burst = None
    landing = None

    found_burst = False
    found_landing = False
    last_point = None

    i = 0
    for entry in log:
        calc_min_max(entry['msg'])
        if not 'altitude' in entry['msg']:
            continue

        if entry['msg']['latitude'] == 0 and entry['msg']['longitude'] == 0:
            continue


        point = Point(entry)

        if i == 0:
            launch = burst = point
        elif point.altitude > burst.altitude and not found_burst:
            burst = point
        elif burst.altitude - point.altitude > 1 and not found_landing:
            found_burst = True
            if not landing or point.altitude < landing.altitude:
                landing = point
            elif abs(point.altitude - landing.altitude) < 0.001 and point.altitude < 1:
                found_landing = True

        flight_path += FLIGHT_PATH.format(point=point)
        if last_point:
            calc_ground_speed(last_point, point)

        last_point = point
        i += 1

    ascent_ms = ((burst.altitude - launch.altitude) * 1000) / (burst.date - launch.date).total_seconds()
    ascent_mph = (ascent_ms / 1609.34) * 3600.0
    descent_ms = ((burst.altitude - landing.altitude) * 1000) / (landing.date - burst.date).total_seconds()
    descent_mph = (descent_ms / 1609.34) * 3600.0

    ground_distance_km = haversine_distance(launch.latitude, launch.longitude,
                                            landing.latitude, landing.longitude)
    flight_time = (landing.date - launch.date).total_seconds()

    ground_speed_kmh['avg'] = ground_distance_km / (flight_time / 3600.0)

    with open('data/stats.json', 'w') as f:
        f.write(json.dumps(dict(ascent_ms=ascent_ms,
                                ascent_mph=ascent_mph,
                                descent_ms=descent_ms,
                                descent_mph=descent_mph,
                                flight_time=flight_time,
                                max_altitude_km=burst.altitude,
                                ground_distance_km=ground_distance_km,
                                ground_speed_kmh=ground_speed_kmh,
                                sensors=sensors), sort_keys=True, indent=4))

    with open('data/hab_path.kml', 'w') as f:
        f.write(BASE_KML.format(flight_path=flight_path,
                                launch=launch,
                                burst=burst,
                                landing=landing,
                                ascent_ms=ascent_ms,
                                descent_ms=descent_ms,
                                flight_time_hr=flight_time/3600.0))

if __name__ == '__main__':
    main()
