import math

def lat2float(value, dir):
    return latlng2float(value, dir, 'S')

def lng2float(value, dir):
    return latlng2float(value, dir, 'W')

def latlng2float(value, dir, negative_dir):
    fval = math.floor(value / 100.0)
    fval += (value - (fval * 100)) / 60
    if dir == negative_dir:
        fval *= -1
    return fval

def gpgga_to_values(sentence):
    values = dict(latitude=0, longitude=0, altitude=0, quality=0,
                  timestamp=(0, 0, 0))

    if len(sentence.timestamp) >= 5:
        values['timestamp'] = (int(sentence.timestamp[0:2]),
                               int(sentence.timestamp[2:4]),
                               float(sentence.timestamp[4:]))

    if len(sentence.latitude) > 0:
        values['latitude'] = lat2float(float(sentence.latitude),
                                  sentence.lat_direction)
    if len(sentence.longitude) > 0:
        values['longitude'] = lng2float(float(sentence.longitude),
                                   sentence.lon_direction)

    if len(sentence.antenna_altitude) > 0:
        values['altitude'] = float(sentence.antenna_altitude) / 1000.0

    values['quality'] = int(sentence.gps_qual)
    return values

def checksum(data):
    ck = 0
    for ch in data:
        ck ^= ord(ch)
    return ck
