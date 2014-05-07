import argparse
from collections import deque
from copy import copy
from datetime import datetime, timedelta
from io import BytesIO
import json
import math
import os
import sys

import cv2
import numpy
from PIL import Image, ImageDraw, ImageFont
import pygal
from pygal.style import Style
from texttable import Texttable

start = datetime(2014, 4, 12, 11, 29)
frame1_start = start + timedelta(seconds=140.76)
launch_date = datetime(2014, 4, 12, 12, 05, 18)

overlay_size = (1280, 36)
chart_width, chart_height = (77, 36)
scale = 1
overlay_scaled = overlay_size
text_size = 24
small_text_size = 18
tiny_text_size = 12
fps = 8.0

bgcolor = (0x32, 0x46, 0x75)
text_color = (150, 144, 131)
ttf = '/Users/marshall/Library/Application Support/skyfonts-google/Arvo regular.ttf'
small_font = ImageFont.truetype(ttf, small_text_size * scale)
tiny_font = ImageFont.truetype(ttf, tiny_text_size * scale)

frame_dir = 'data/stats_frames'
frame_deltas = []

launch = None
last_entry = None
last_time = None
last_altitude, last_int_temp, last_int_humidity, last_ext_temp, last_ascent, last_ground_speed = (0, 0, 0, 0, 0, 0)
last_entries = deque([], 5)
altitudes = deque([], 50)
ascent_rates = deque([], 50)
last_altitudes = None
last_chart = None
positions = None
sizes = None

_FORMAT_TABLE = (
    (u'Altitude', u'Ascent Rate', u'Int. Temp',
     u'Int. Humidity', u'Ext. Temp', u'Ground Speed'),

    (u'{altitude:.0f} ft', u'{ascent:+.1f} ft/s', u'{int_temp:+.1f} F',
     u'{int_humidity:.1f}%', u'{ext_temp:+.1f} F', u'{ground_speed:.0f} mph')
)

FORMAT_TABLE = (
    (u'Altitude', u'{altitude:.0f} ft'),
    (u'Ascent', u'{ascent:+.1f} ft/s'),
    (u'Int. Temp', u'{int_temp:+.1f} F'),
    (u'Int. Humid', u'{int_humidity:.1f}%'),
    (u'Ext. Temp', u'{ext_temp:+.1f} F'),
    (u'Grnd Speed', u'{ground_speed:.0f} mph')
)

def gen_table(**kwargs):
    all_rows = []
    for row in FORMAT_TABLE:
        final_row = []
        all_rows.append(final_row)
        for column in row:
            final_row.append(column.format(**kwargs))

    return all_rows
    '''table = Texttable(max_width=28)
    table.set_deco(0)
    table.set_cols_align(['l'] * len(FORMAT_TABLE[0]))
    table.add_rows(all_rows, header=False)
    return table.draw()'''


chart_bgcolor = '#324675'
altitudes_style = Style(background=chart_bgcolor, plot_background=chart_bgcolor,
                        colors=('#CF8A00',))
ascents_style = Style(background=chart_bgcolor, plot_background=chart_bgcolor,
                      colors=('#FFC757',))

def gen_chart():
    global altitudes, ascent_rates, last_altitudes, last_charts
    if last_altitudes == altitudes:
        return last_charts

    altitudes_chart, ascents_chart = pygal.Line(), pygal.Line()
    altitudes_chart.add('altitude', altitudes)
    ascents_chart.add('ascent rate', ascent_rates)
    kwargs = dict(width=chart_width,
                  height=chart_height,
                  show_dots=False,
                  print_values=False,
                  fill=True,
                  no_data_text='')

    altitudes_sparkline = altitudes_chart.render_sparkline(style=altitudes_style, **kwargs)
    ascents_sparkline = ascents_chart.render_sparkline(style=ascents_style, **kwargs)

    import cairosvg
    png_bytes0 = cairosvg.svg2png(bytestring=altitudes_sparkline)
    png_bytes1 = cairosvg.svg2png(bytestring=ascents_sparkline)
    last_charts = (Image.open(BytesIO(png_bytes0)),
                   Image.open(BytesIO(png_bytes1)))
    last_altitudes = copy(altitudes)
    return last_charts

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

def fahrenheit(t):
    return (t * 9 / 5.0) + 32

def km_to_feet(km):
    return km * 1000 * 3.28084

def km_to_miles(km):
    return km * 0.621371

def gen_frame(frame_index, frame_time, entry=None):
    global launch, last_altitude, last_entry, last_int_temp, last_int_humidity, \
           last_ext_temp, last_ascent, last_time, last_ground_speed, last_entries, \
           altitudes, ascent_rates, positions, sizes

    if entry:
        msg = entry['msg']
        if 'int_temperature' in msg and msg['int_temperature'] <= 40:
            last_int_temp = fahrenheit(msg['int_temperature'])
            last_int_humidity = msg['int_humidity']

        if 'ext_temperature' in msg:
            last_ext_temp = fahrenheit(msg['ext_temperature'])

        if 'altitude' in msg and msg['latitude'] != 0 and msg['longitude'] != 0:
            new_altitude = km_to_feet(msg['altitude'])
            if launch is None:
                launch = entry
            else:
                last_msg = last_entries[0]['msg']
                last_altitude = km_to_feet(last_msg['altitude'])
                distance_km = haversine_distance(last_msg['latitude'], last_msg['longitude'],
                                                 msg['latitude'], msg['longitude'])
                time_delta = frame_time - (start + timedelta(seconds=last_entries[0]['time']))
                last_ground_speed = km_to_miles(distance_km) / (time_delta.total_seconds() / 3600.0)
                last_ascent = (new_altitude - last_altitude) / time_delta.total_seconds()

            last_altitude = new_altitude
            altitudes.append(new_altitude)
            ascent_rates.append(last_ascent)
            last_entries.append(entry)

    image = Image.new('RGBA', overlay_scaled, bgcolor)
    draw = ImageDraw.Draw(image)

    time = u'{date:%H:%M:%S}'.format(date=frame_time)
    time_size = draw.textsize(time, font=tiny_font)
    text_begin = (2, 2 * scale)

    table_begin = (2, 2 * scale)
    rows = gen_table(altitude=last_altitude,
                     int_temp=last_int_temp,
                     int_humidity=last_int_humidity,
                     ext_temp=last_ext_temp,
                     ascent=last_ascent,
                     ground_speed=last_ground_speed)

    if positions is None:
        sizes = [draw.textsize('Altitude XXXXX ft', font=small_font),
                 draw.textsize('Ascent +XXX.X ft/s', font=small_font),
                 draw.textsize('Int. Temp +XXX.X F', font=small_font),
                 draw.textsize('Int. Humid XXX.X%', font=small_font),
                 draw.textsize('Ext. Temp +XXX.X F', font=small_font),
                 draw.textsize('Grnd Speed XX mph', font=small_font)]

        sizes[0] = (sizes[0][0] + chart_width + 2, sizes[0][1])
        sizes[1] = (sizes[1][0] + chart_width + 2, sizes[1][1])
        mid_y = (overlay_size[1] - small_text_size) / 2
        begin_x = 10
        positions = []
        for size in sizes:
            positions.append((begin_x, mid_y))
            begin_x += size[0] + 5

    row_colors = ((207, 138, 0), (255, 199, 87))
    row_index = 0
    for row in rows:
        row_color = row_colors[row_index % len(row_colors)]
        text = row[0] + ' ' + row[1]
        text_size = draw.textsize(text, font=small_font)
        draw.text(positions[row_index], text, row_color, font=small_font)
        table_begin = (table_begin[0] + text_size[0] + 10, table_begin[1])
        row_index += 1

    altitude_pos = (positions[0][0] + sizes[0][0] - chart_width, 2)
    ascent_pos = (positions[1][0] + sizes[1][0] - chart_width, 2)
    altitude_image, ascent_image = gen_chart()
    image.paste(altitude_image, altitude_pos)
    image.paste(ascent_image, ascent_pos)
    image.save(os.path.join(frame_dir, '%05d.png' % frame_index), 'PNG')
    if entry:
        last_entry = entry
        last_time = frame_time

    return image

def gen_frames(log, frame_start=0, frame_end=-1):
    duration_sec = log[-1]['time'] - log[0]['time']
    total_frames = 0
    frame_index = 0

    def generator(i, frame_index, entry):
        def wrapper():
            frame_time = start + timedelta(seconds=entry['time'] + (i / fps))
            print_progress(frame_index, total_frames)
            gen_frame(frame_index, frame_time, entry=entry if i == 0 else None)
        return wrapper

    generators = []
    for e in range(len(log)):
        entry = log[e]
        entry_frame_count = 1
        if e < len(log) - 1:
            next_entry = log[e + 1]
            entry_frame_count = max(int(round((next_entry['time'] - entry['time']) * fps)), 1)

        for i in range(entry_frame_count):
            generators.append(generator(i, frame_index, entry))
            frame_index += 1
            total_frames += 1

    for gen in generators[frame_start:frame_end]:
        gen()

def print_progress(i, total):
    sys.stdout.write('\rFrame %d / %d (%0.2f%%)' % \
                     (i, total, (100.0 * i / float(total))))
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frame-start', type=int, default='0', help='Frame number to start on. default: 0')
    parser.add_argument('--frame-end', type=int, default='-1', help='Number of frames to process. default: -1 (all)')
    args = parser.parse_args()

    global total
    if not os.path.exists(frame_dir):
        os.makedirs(frame_dir)

    log = json.load(open('data/obc_log.json'))
    gen_frames(log, frame_start=args.frame_start, frame_end=args.frame_end)

if __name__ == '__main__':
    main()
