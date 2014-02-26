import argparse
import logging, logging.handlers
import os

def main():
    import log
    import obc
    import radio

    log.setup()
    parser = argparse.ArgumentParser()
    parser.add_argument('--tcp', action='store_true', default=False)
    args = parser.parse_args()

    radio_type = radio.TCPRadio if args.tcp else radio.Radio
    obc.OBC(radio_type=radio_type).main_loop()

if __name__ == '__main__':
    main()
