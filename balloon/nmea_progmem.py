#!/usr/bin/env python

import os
import sys

data = open(sys.argv[1], "r").read()
var = sys.argv[2] if len(sys.argv) > 2 else "str"

print """
/** WARNING this is generated from nmea_progmem.py */
#ifndef _%(varupper)s_H
#define _%(varupper)s_H

#include <stdint.h>
#include <avr/pgmspace.h>

#ifdef __cplusplus
extern "C" {
#endif

""" % { "varupper": var.upper() }

count = 0
max_len = 0
lines = filter(lambda l: len(l) > 0, [l.strip() for l in data.splitlines()])
total = len(lines)
dwidth = "%%0%dd" % len(str(total))

for line in lines:
    print "static char %s_%s[] PROGMEM = \"%s\";" % (var, dwidth % count, line)
    count += 1
    max_len = max(len(line), max_len)

print "static const char *%s[] PROGMEM = {" % var
for i in range(count):
    print "    %s_%s," % (var, dwidth % i)
print "};"

print """
const uint16_t %(var)sLength = %(count)d;
const uint16_t %(var)sMaxStringLength = %(max_len)d;

#ifdef __cplusplus
}
#endif
#endif // defined %(varupper)s_H
""" % {
    "var": var, "count": count, "max_len": max_len, "varupper": var.upper()
}
