from collections import namedtuple
import logging
import struct

import hab_utils

''' PEPPER-2 binary protocol

                   ord('P') + ord('M')  ord('S') + ord('G')
bytes 0 .. 1     : 0x9d9a (begin msg)
byte  2          : Message type (uint8_t)
byte  3          : Length of data segment (uint8_t)
bytes 4 .. 7     : CRC32 of data (uint32_t)
bytes 8 .. N     : Message data
                   ord('P') + ord('E')  ord('N') + ord('D')
bytes N+1 .. N+2 : 0x9592 (end msg)
'''

class BadMarker(Exception):
    def __init__(self, got, expected):
        super(BadMarker, self).__init__('Bad marker. Got 0x%04X, expected 0x%04X' % (got, expected))

class BadMsgType(Exception):
    def __init__(self, msg_type):
        super(BadMsgType, self).__init__('Bad message type %d' % msg_type)

class BadChecksum(Exception):
    def __init__(self, got, expected):
        super(BadChecksum, self).__init__('Bad checksum. Got 0x%08X, expected 0x%08X' % (got, expected))

msg_types = {}
def msg_type(type_id):
    global msg_types
    def wrapper(msg_type):
        msg_type.TYPE = type_id
        msg_types[type_id] = msg_type
        return msg_type
    return wrapper

log = logging.getLogger('proto')

class Msg(object):
    TYPE = -1
    data_struct = None
    data_attrs  = None

    begin = 0x9d9a # 'PMSG'
    begin_len = 2

    end = 0x9592 # 'PEND'
    end_len = 2

    marker_struct = struct.Struct('!H')
    header_struct = struct.Struct('!BBL')
    header_tuple  = namedtuple('Header', ['msg_type', 'msg_len', 'msg_crc32'])

    max_data_len = 255
    max_msg_len = begin_len + header_struct.size + end_len + max_data_len
    header_end = begin_len + header_struct.size

    @classmethod
    def validate_header(cls, buf):
        if not isinstance(buf, (str, buffer)):
            buf = buffer(buf)

        begin = cls.marker_struct.unpack_from(buf)
        if not begin or begin[0] != cls.begin:
            raise BadMarker(begin[0], cls.begin)

    @classmethod
    def from_header_buffer(cls, buf):
        global msg_types
        if not isinstance(buf, (str, buffer)):
            buf = buffer(buf)

        cls.validate_header(buf)
        header = cls.header_tuple._make(cls.header_struct.unpack_from(buf, cls.begin_len))
        if header.msg_type not in msg_types:
            raise BadMsgType(header.msg_type)

        msg = msg_types[header.msg_type](buf=buf)
        return msg

    @classmethod
    def from_data(cls, **kwargs):
        if not cls.data_struct:
            return cls(msg_data='')

        for key, val in cls.data_attrs:
            if key not in kwargs:
                kwargs[key] = val

        try:
            args = [kwargs.get(a[0], a[1]) for a in cls.data_attrs]
            return cls(msg_data=cls.data_struct.pack(*args))
        except:
            log.error('Invalid data for %s struct %s: %s', cls.__name__,
                                                           cls.data_struct.format,
                                                           str(args))
            return None

    def __init__(self, buf=None, msg_data=None):
        self._buffer = buf or bytearray(self.max_msg_len)
        self._buffer_ro = buffer(self._buffer)
        self._buffer_len = 0
        self.header_valid = False
        self.data_valid = False
        self.data_view = None

        self.data_tuple = None
        if self.data_attrs:
            self.data_tuple = namedtuple(self.__class__.__name__, (a[0] for a in self.data_attrs))

        if msg_data is not None:
            self.pack_data(msg_data)

    def __str__(self):
        return '%s[%d](%s)' % (self.__class__.__name__,
                               self._buffer_len,
                               self.data_attr_str())

    def data_attr_str(self):
        if not self.data_attrs:
            return ''

        attr_strs = []
        for name, _ in self.data_attrs:
            attr_strs.append('%s=%s' % (name, repr(getattr(self, name))))

        return ', '.join(attr_strs)

    def data_str(self):
        return ' '.join(['%x' % ord(c) for c in self._buffer[:self._buffer_len]])

    def pack_data(self, msg_data):
        msg_data = msg_data or ''
        self.marker_struct.pack_into(self._buffer, 0, self.begin)
        self.header_struct.pack_into(self._buffer, self.begin_len, self.TYPE,
                                     len(msg_data), hab_utils.crc32(msg_data))

        data_end = self.header_end + len(msg_data)
        self._buffer[self.header_end:data_end] = msg_data
        self.marker_struct.pack_into(self._buffer, data_end, self.end)
        self._get_header()
        self.validate_data()

    def as_buffer(self):
        return buffer(self._buffer, 0, self._buffer_len)

    def _get_header(self, check_begin=True):
        global msg_types
        if check_begin and not self.header_valid:
            self.validate_header(self._buffer)
            values = self.header_struct.unpack_from(self._buffer_ro, self.begin_len)
            header = self.header_tuple._make(values)
            if header.msg_type not in msg_types:
                raise BadMsgType(header.msg_type)

            self.header = header
            self.header_valid = True

        return self.header

    def _get_data(self):
        if not self.data_valid:
            self.validate_data()
            self.data_valid = True

        return self.data_view

    def __getattr__(self, attr):
        attrs = self.data_tuple._make(self.data_struct.unpack_from(self.msg_data))
        return getattr(attrs, attr)

    def validate_data(self):
        msg_type, msg_len, msg_crc32 = self._get_header()
        self.data_view = buffer(self._buffer, self.header_end, msg_len)
        crc32 = hab_utils.crc32(self.data_view)
        if crc32 != msg_crc32:
            raise BadChecksum(crc32, msg_crc32)

        data_len = self.header_end + msg_len
        self._buffer_len = data_len + self.end_len
        end = self.marker_struct.unpack_from(self._buffer_ro, data_len)
        if not end or end[0] != self.end:
            raise BadMarker(end[0], self.end)

    @property
    def msg_header(self):
        return self._get_header()

    @property
    def msg_type(self):
        return self.msg_header.msg_type

    @property
    def msg_len(self):
        return self.msg_header.msg_len

    @property
    def msg_crc32(self):
        return self.msg_header.msg_crc32

    @property
    def msg_data(self):
        return self._get_data()

@msg_type(0)
class LocationMsg(Msg):
    data_struct = struct.Struct('!ddfBBf')
    data_attrs  = (('latitude', 0), ('longitude', 0), ('altitude', 0),
                   ('quality', 0), ('satellites', 0), ('speed', 0))

@msg_type(1)
class TelemetryMsg(Msg):
    modes = ('preflight', 'ascent', 'descent', 'landed')
    mode_preflight  = 0
    mode_ascent     = 1
    mode_descent    = 2
    mode_landed     = 3
    cpu_unknown     = 127
    temp_unknown    = -999.999

    data_struct = struct.Struct('!LBBHfff')
    data_attrs  = (('uptime', 0), ('mode', mode_preflight), ('cpu_usage', cpu_unknown),
                   ('free_mem', 0), ('int_temperature', temp_unknown), ('int_humidity', temp_unknown),
                   ('ext_temperature', temp_unknown))

@msg_type(2)
class DroidTelemetryMsg(Msg):
    accel_states  = ('level', 'rising', 'falling')
    accel_level   = 0
    accel_rising  = 1
    accel_falling = 2

    data_struct = struct.Struct('!BBBHHdd')
    data_attrs  = (('battery', 0), ('radio', 0), ('accel_state', 0),
                   ('accel_duration', 0), ('photo_count', 0), ('latitude', 0),
                   ('longitude', 0))

@msg_type(3)
class PhotoDataMsg(Msg):
    data_struct = struct.Struct('!HHHL')
    data_attrs = (('index', 0), ('chunk', 0), ('chunk_count', 0),
                  ('file_size', 0))

    @classmethod
    def from_data(cls, index=0, chunk=0, chunk_count=0, file_size=0, photo_data=''):
        header = cls.data_struct.pack(index, chunk, chunk_count, file_size)
        return cls(msg_data=header+photo_data)

    @property
    def photo_data(self):
        data = self.msg_data
        return buffer(self.msg_data, self.data_struct.size,
                      self.msg_len - self.data_struct.size)

@msg_type(10)
class StartPhotoDataMsg(Msg):
    data_struct = struct.Struct('!H')
    data_attrs = ('index')

@msg_type(11)
class StopPhotoDataMsg(Msg):
    pass

@msg_type(12)
class SendTextMsg(Msg):
    pass

@msg_type(13)
class AddPhoneNumberMsg(Msg):
    @classmethod
    def from_phone_number(cls, phone_number):
        return cls(msg_data=struct.pack('!%ds' % len(phone_number), phone_number))

    @property
    def phone_number(self):
        return str(self.msg_data[:])

class MsgReader(object):
    state_header = 0
    state_data   = 1
    state_end    = 2

    def __init__(self):
        self.log = logging.getLogger('msg_reader')
        self.buffer = bytearray(Msg.max_msg_len)
        self.reset()

    def reset(self):
        self.state = self.state_header
        self.msg = None
        self.index = 0

    def read(self, f):
        while self.state != self.state_end:
            b = f.read(1)
            if b == '':
                return None

            self.buffer[self.index] = b
            self.index += 1

            if self.state == self.state_header:
                self.handle_header_byte()
            elif self.state == self.state_data:
                self.handle_data_byte()

        self.state = self.state_header
        self.index = 0
        return self.msg

    def handle_header_byte(self):
        if self.index != Msg.header_end:
            return

        try:
            self.msg = Msg.from_header_buffer(self.buffer)
            self.state = self.state_data

            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug('HEADER: %s[%d] = %s', self.msg.__class__.__name__,
                                                      self.msg.msg_len,
                                                      ' '.join(('%x' % c for c in self.buffer[:Msg.header_end])))
        except BadMarker, e:
            self.log.warn('Bad start marker, discarding %d out of sync bytes: %s', self.index,
                          ' '.join(('%x' % c for c in self.buffer[:Msg.header_end])))
            self.index = 0
            raise

    def handle_data_byte(self):
        if self.index != Msg.header_end + self.msg.msg_len + Msg.end_len:
            return

        try:
            self.msg.validate_data()
            self.state = self.state_end
        except (BadMarker, BadChecksum) as e:
            self.log.warn('%s, discarding %d out of sync bytes',
                          e.__class__.__name__, self.index)
            self.index = 0
            self.state = self.state_header
            raise
