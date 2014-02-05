import argparse
import logging
import os

def setup_logging():
    logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                        level=logging.INFO)

def main():
    import obc
    import radio
    setup_logging()

    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument('--tcp', action='store_true', default=False)
    args = parser.parse_args()

    radio_type = radio.TCPRadio if args.tcp else radio.Radio
    obc.OBC(radio_type=radio_type).main_loop()

if __name__ == '__main__':
    main()
