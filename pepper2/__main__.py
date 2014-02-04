import argparse
import radio
import obc

parser = argparse.ArgumentParser()
parser.add_argument('--tcp', action='store_true', default=False)
args = parser.parse_args()

radio_type = radio.TCPRadio if args.tcp else radio.Radio
obc.OBC(radio_type=radio_type).main_loop()
