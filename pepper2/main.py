import argparse
import logging, logging.handlers
import os
import sys

def main():
    import log
    import obc
    import radio
    import gevent

    log.setup()
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument('--tcp', action='store_true', default=False)

    argv = sys.argv[1:]
    if os.path.exists('/etc/pepper2.conf'):
        argv += ['@/etc/pepper2.conf']
    args = parser.parse_args(argv)

    radio_type = radio.TCPServerRadio if args.tcp else radio.Radio
    p2_obc = obc.OBC(radio_type=radio_type)
    p2_obc.start()
    p2_obc.join()

if __name__ == '__main__':
    main()
