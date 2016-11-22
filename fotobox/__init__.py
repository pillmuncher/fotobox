#!/usr/bin/env python
# coding: utf-8

if __name__ == '__main__':
    import sys
    import argparse
    from . import config
    from . import run
    parser = argparse.ArgumentParser(description='FotoBox Programm.')
    parser.add_argument(
        'filename',
        default='fotobox.json',
        metavar='c',
        type=str,
        help='path to config file'
    )
    sys.exit(run(config(parser.parse_args().filename)))
