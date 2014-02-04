import argparse
import logging
import os

this_dir = os.path.abspath(os.path.dirname(__file__))

logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
                    level=logging.INFO)

def main():
    import radio
    import obc

    parser = argparse.ArgumentParser()
    parser.add_argument('--tcp', action='store_true', default=False)
    args = parser.parse_args()

    radio_type = radio.TCPRadio if args.tcp else radio.Radio
    obc.OBC(radio_type=radio_type).main_loop()

if __name__ == '__main__':
    main()
