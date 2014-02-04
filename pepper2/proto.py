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
    def validate_header(cls, buffer):
        begin = cls.marker_struct.unpack_from(buffer)
        if not begin or begin[0] != cls.begin:
            raise BadMarker(begin[0], cls.begin)


    @classmethod
    def from_header_buffer(cls, buffer):
        global msg_types
        cls.validate_header(buffer)
        header = cls.header_tuple._make(cls.header_struct.unpack_from(buffer, cls.begin_len))
        if header.msg_type not in msg_types:
            raise BadMsgType(header.msg_type)

        msg = msg_types[header.msg_type](buf=buffer)
        return msg

    @classmethod
    def from_data(cls, **kwargs):
        if not cls.data_struct:
            return cls(msg_data='')

        for key, val in cls.data_attrs:
            if key not in kwargs:
                kwargs[key] = val

        return cls(msg_data=cls.data_struct.pack(*(kwargs[a[0]] for a in cls.data_attrs)))

    def __init__(self, buf=None, msg_data=None):
        self.buffer = buf or bytearray(self.max_msg_len)
        self.buffer_len = 0
        self.header_valid = False
        self.data_valid = False
        self.data_view = None

        self.data_tuple = None
        if self.data_attrs:
            self.data_tuple = namedtuple(self.__class__.__name__, (a[0] for a in self.data_attrs))

        if msg_data is not None:
            self.pack_data(msg_data)

    def pack_data(self, msg_data):
        msg_data = msg_data or ''
        self.marker_struct.pack_into(self.buffer, 0, self.begin)
        self.header_struct.pack_into(self.buffer, self.begin_len, self.TYPE,
                                     len(msg_data), hab_utils.crc32(msg_data))

        data_end = self.header_end + len(msg_data)
        self.buffer[self.header_end:data_end] = msg_data
        self.marker_struct.pack_into(self.buffer, data_end, self.end)
        self._get_header()
        self.validate_data()

    def as_buffer(self):
        return buffer(self.buffer, 0, self.buffer_len)

    def _get_header(self, check_begin=True):
        global msg_types
        if check_begin and not self.header_valid:
            self.validate_header(self.buffer)
            header = self.header_tuple._make(self.header_struct.unpack_from(self.buffer, self.begin_len))
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
        self.data_view = buffer(self.buffer, self.header_end, msg_len)
        crc32 = hab_utils.crc32(self.data_view)
        if crc32 != msg_crc32:
            raise BadChecksum(crc32, msg_crc32)

        data_len = self.header_end + msg_len
        self.buffer_len = data_len + self.end_len
        end = self.marker_struct.unpack_from(self.buffer, data_len)
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
    data_struct = struct.Struct('!ddfB')
    data_attrs  = (('latitude', 0), ('longitude', 0), ('altitude', 0),
                   ('quality', 0))

@msg_type(1)
class TelemetryMsg(Msg):
    data_struct = struct.Struct('!LBBHff')
    data_attrs  = (('uptime', 0), ('mode', 0), ('cpu_usage', 0),
                   ('free_mem', 0), ('temperature', 0), ('humidity', 0))

@msg_type(2)
class DroidTelemetryMsg(Msg):
    data_struct = struct.Struct('!BBHddf')
    data_attrs  = (('battery', 0), ('radio', 0), ('photo_count', 0),
                   ('latitude', 0), ('longitude', 0), ('altitude', 0))

@msg_type(3)
class PhotoDataMsg(Msg):
    data_struct = struct.Struct('!BHHL')
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
    data_struct = struct.Struct('!B')
    data_attrs = ('index')

@msg_type(11)
class StopPhotoDataMsg(Msg):
    pass

@msg_type(12)
class SendTextMsg(Msg):
    pass

class MsgReader(object):
    state_header = 0
    state_data   = 1
    state_end    = 2

    def __init__(self):
        self.log = logging.getLogger('msg_reader')
        self.state = self.state_header
        self.msg = None
        self.buffer = bytearray(Msg.max_msg_len)
        self.index = 0

    def read(self, f):
        self.state = self.state_header
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
        except BadMarker, e:
            self.log.warn('Bad start marker, discarding %d out of sync bytes', self.index)
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


