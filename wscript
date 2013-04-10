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
    ctx.add_option('--arduino', help='Arduino directory (default %default)', default='/Applications/Arduino.app')
    ctx.add_option('--port', help='Arduino USB port (default %default)', default='/dev/tty.usbmodem*')
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

    arduino = cfg.options.arduino
    if platform.system() == 'Darwin':
        arduino_hardware = os.path.join(arduino, 'Contents', 'Resources',
                                        'Java', 'hardware')
    else:
        print >>sys.stderr, 'Unsure how to build arduino paths for %s' % platform.system()
        sys.exit(1)

    env.ARDUINO_BIN = os.path.join(arduino_hardware, 'tools', 'avr', 'bin')
    env.ARDUINO_CORE = os.path.join(arduino_hardware, 'arduino', 'cores', 'arduino')
    env.ARDUINO_VARIANTS = os.path.join(arduino_hardware, 'arduino', 'variants')

    env.PORT = cfg.options.port
    env.MCU = cfg.options.mcu
    env.FORMAT = cfg.options.format
    env.FCPU = cfg.options.fcpu
    env.PROGRAMMER = cfg.options.programmer
    env.VARIANT = 'mega' if cfg.options.mcu.startswith('atmega') else 'standard'

    env.CC = env.ARDUINO_BIN + '/avr-gcc'
    env.AR = env.ARDUINO_BIN + '/avr-ar'
    env.CXX = env.ARDUINO_BIN + '/avr-g++'
    env.OBJCOPY = env.ARDUINO_BIN + '/avr-objcopy'

    cfg.load('gcc g++')
    cfg.find_program('avrdude', var='AVRDUDE')

    env.append_value('LINKFLAGS', ['-Wl,--gc-sections,--relax', '-mmcu=%s' % env.MCU])
    env.append_value('LIBS', ['m'])

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
    print env.ARDUINO_CORE

    sources = bld.path.ant_glob('balloon/*.cpp')
    sources.extend(bld.root.ant_glob([
        env.ARDUINO_CORE[1:] + '/*.c',
        env.ARDUINO_CORE[1:] + '/*.cpp',
    ]))

    bld.program(target=BALLOON_TARGET+'.elf',
        source=sources,
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
