#!/usr/bin/env python
# encoding: utf-8
import os
import platform
import sys

from waflib.Build import BuildContext

NAME = 'pepper'
VERSION = 1
BALLOON_TARGET = '%s%d-balloon' % (NAME, VERSION)

top = '.'
out = 'build'

def options(ctx):
    if platform.system() == 'Darwin':
        default_arduino = '/Applications/Arduino.app'
        default_tty = '/dev/tty.usbmodem*'
    else:
        default_arduino = '/usr/share/arduino'
        default_tty = '/dev/ttyACM*'

    ctx.add_option('--arduino', help='Arduino directory (default %default)', default=default_arduino)
    ctx.add_option('--toolchain', help='Directory for the avr-* executables', default=None)
    ctx.add_option('--port', help='Arduino USB port (default %default)', default=default_tty)
    ctx.add_option('--mcu', help='Target Arduino MCU (default %default)', default='atmega2560')
    ctx.add_option('--fcpu', help='F_CPU rate (default %default)', type=long, default=16000000)
    ctx.add_option('--format', help='Output format (default %default)', default='ihex')
    ctx.add_option('--programmer', help='AVRDude programmer (default %default)', default='stk500')
    ctx.add_option('--debug', help='Build debug symbols (default %default)', action='store_true', default=False)

def configure(cfg):
    configure_balloon(cfg)
    configure_ground(cfg)

def configure_balloon(cfg):
    cfg.setenv('balloon')
    env = cfg.env

    cfg.start_msg('Checking for Arduino')
    arduino = cfg.options.arduino
    arduino_lib = os.path.join(arduino, 'lib')
    if not os.path.exists(arduino_lib) and platform.system() == 'Darwin':
        arduino = os.path.join(arduino, 'Contents', 'Resources', 'Java')
        arduino_lib = os.path.join(arduino, 'lib')

    if not os.path.exists(arduino_lib):
        cfg.fatal('Arduino "lib" is missing: %s' % arduino_lib)

    version_txt = os.path.join(arduino_lib, 'version.txt')
    if not os.path.exists(version_txt):
        cfg.fatal('Arduino "version.txt" is missing: %s' % version_txt)

    arduino_version = open(version_txt, 'r').read().strip()
    env.ARDUINO_VERSION = [int(x) for x in arduino_version.split('.')]
    cfg.end_msg('%s (%s)' % (arduino, arduino_version))

    arduino_hardware = os.path.join(arduino, 'hardware')
    if not os.path.exists(arduino_hardware):
        cfg.fatal('Arduino "hardware" is missing: %s' % arduino_hardware)

    env.ARDUINO_BIN = os.path.join(arduino_hardware, 'tools', 'avr', 'bin')

    hw_arduino = os.path.join(arduino_hardware, 'arduino')
    if env.ARDUINO_VERSION[0] >= 1 and env.ARDUINO_VERSION[1] >= 5:
        hw_arduino = os.path.join(hw_arduino, 'avr')

    env.ARDUINO_HARDWARE = hw_arduino
    env.ARDUINO_CORE = os.path.join(hw_arduino, 'cores', 'arduino')
    env.ARDUINO_VARIANTS = os.path.join(hw_arduino, 'variants')

    if platform.system() == 'Darwin':
        default_toolchain = env.ARDUINO_BIN
    else:
        default_toolchain = '/usr/bin'

    env.PORT = cfg.options.port
    env.MCU = cfg.options.mcu
    env.FORMAT = cfg.options.format
    env.FCPU = cfg.options.fcpu
    env.PROGRAMMER = cfg.options.programmer
    env.VARIANT = 'mega' if cfg.options.mcu.startswith('atmega') else 'standard'

    avr_paths = [env.ARDUINO_BIN]
    avr_paths.extend(os.environ['PATH'].split(os.pathsep))

    cfg.find_program('avr-gcc', var='CC', path_list=avr_paths)
    cfg.find_program('avr-ar', var='AR', path_list=avr_paths)
    cfg.find_program('avr-g++', var='CXX', path_list=avr_paths)
    cfg.find_program('avr-objcopy', var='OBJCOPY', path_list=avr_paths)
    cfg.load('gcc g++')
    cfg.find_program('avrdude', var='AVRDUDE')

    env.append_value('LINKFLAGS', ['-Wl,--gc-sections,--relax', '-mmcu=%s' % env.MCU])
    env.append_value('LIB', ['c', 'm', 'c'])

    env.ARDUINO_VERSION = '101'
    balloon_cflags = ['-Wall', '-Os', '-fno-exceptions', '-ffunction-sections',
                      '-fdata-sections', '-mmcu=%s' % env.MCU,
                      '-DF_CPU=%sL' % env.FCPU, '-DARDUINO=%s' % env.ARDUINO_VERSION,
                      '-DUSB_VID=null', '-DUSB_PID=null']

    if cfg.options.debug:
        balloon_cflags.append('-g')

    env.append_value('CFLAGS', balloon_cflags)
    env.append_value('CXXFLAGS', balloon_cflags)
    env.append_value('INCLUDES', [env.ARDUINO_CORE, env.ARDUINO_VARIANTS + '/' + env.VARIANT])

def configure_ground(cfg):
    pass

def build(bld):
    build_balloon(bld)
    build_ground(bld)

def build_balloon(bld):
    env = bld.env_of_name('balloon')

    nmea_sentences = bld.path.make_node('build/nmea_sentences.c')
    bld(rule='../balloon/nmea_progmem.py ${SRC} kSentences > ${TGT}',
        source='data/cubesat.nmea', target=nmea_sentences, always=True)

    arduino_libraries = [
        env.ARDUINO_HARDWARE + '/libraries/SoftwareSerial',
        'balloon/lib/Adafruit-GPS-Library'
    ]

    sources = bld.path.ant_glob(['balloon/*.cpp'])
    sources.append(nmea_sentences)
    includes = ['.']

    for lib in arduino_libraries:
        if lib.startswith(env.ARDUINO_HARDWARE):
            sources.extend(bld.root.ant_glob(lib[1:] + '/*.cpp'))
        else:
            sources.extend(bld.path.ant_glob(lib + '/*.cpp'))

        includes.append(lib)

    sources.extend(bld.root.ant_glob([
        env.ARDUINO_CORE[1:] + '/**/*.c',
        env.ARDUINO_CORE[1:] + '/**/*.cpp',
    ]))

    bld.program(target=BALLOON_TARGET+'.elf',
        source=sources,
        includes=includes,
        env=env)

    bld(rule='${OBJCOPY} -R .eeprom -O ${FORMAT} ${SRC} ${TGT}',
        source=BALLOON_TARGET+'.elf', target=BALLOON_TARGET+'.hex', env=env)

    bld(rule='${OBJCOPY} -j .eeprom --no-change-warnings ' \
             '--change-section-lma .eeprom=0 -O ihex ${SRC} ${TGT}',
        source=BALLOON_TARGET+'.elf', target=BALLOON_TARGET+'.eeprom', env=env)

def build_ground(bld):
    pass

def program(bld):
    bld(rule='${AVRDUDE} -F -p ${MCU} -P ${PORT} -c ${PROGRAMMER} ' \
             '-U flash:w:${SRC}', source=BALLOON_TARGET+'.hex',
        env=bld.env_of_name('balloon'))

class Program(BuildContext):
    cmd = 'program'
    fun = 'program'
