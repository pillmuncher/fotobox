#!/usr/bin/env python
# coding: utf-8

import json
import os.path
import queue
import threading

from functools import partial

from PIL import Image

from .fotobox import main


class Config(object):
    def __init__(self, conf):
        for k, v in conf.iteritems():
            if isinstance(v, dict):
                setattr(self, k, Config(v))
            elif isinstance(v, list):
                setattr(self, k, tuple(v))
            else:
                setattr(self, k, v)


def config(file_name):

    def photo_length(total, padding, margin_a, margin_b):
        return (total - (margin_a + padding + margin_b)) // 2

    def get_box(n, pad_width, pad_height):
        col, row = divmod(n, 2)
        left = c.montage.margin.left + pad_width * col
        right = left + c.montage.photo.width
        upper = c.montage.margin.top + pad_height * row
        lower = upper + c.montage.photo.height
        return left, upper, right, lower

    with open(file_name, 'r') as config_file:
        c = Config(json.load(config_file))

    resource_path = partial(os.path.join, c.resource_path)

    c.photo.range = range(4)
    c.photo.size = c.photo.width, c.photo.height
    c.photo.countdown.prepare.image_mask = resource_path(
        c.photo.countdown.prepare.image_mask,
    )
    c.photo.countdown.count.sound_mask = resource_path(
        c.photo.countdown.count.sound_mask,
    )
    c.photo.countdown.count.image_mask = resource_path(
        c.photo.countdown.count.image_mask,
    )
    c.photo.countdown.smile.image_file = resource_path(
        c.photo.countdown.smile.image_file,
    )
    c.screen.size = c.screen.width, c.screen.height
    c.screen.rect = 0, 0, c.screen.width, c.screen.height
    c.montage.photo = Config({})
    c.montage.photo.width = photo_length(
        c.screen.width,
        c.montage.margin.padding,
        c.montage.margin.left,
        c.montage.margin.right,
    )
    c.montage.photo.height = photo_length(
        c.screen.height,
        c.montage.margin.padding,
        c.montage.margin.top,
        c.montage.margin.bottom,
    )
    c.montage.photo.size = c.montage.photo.width, c.montage.photo.height
    pad_width = c.montage.photo.width + c.montage.padding
    pad_height = c.montage.photo.height + c.montage.padding
    c.montage.photo.box = [
        get_box(i, pad_width, pad_height) for i in c.photo.range
    ]
    c.montage.image = Image.new('RGBA', c.screen.size, c.montage.background)
    c.montage.watermark.image = (
        Image
        .open(c.montage.watermark.image_file)
        .resize(c.screen.size, Image.ANTIALIAS)
    )
    c.printout.logo.image_file = resource_path(
        c.printout.logo.image_file,
    )
    c.printout.logo.image = Image.open(c.printout.logo.image_file)
    c.shooting_lock = threading.Lock()
    c.exit_code = queue.Queue(maxsize=1)
    return c


if __name__ == '__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='FotoBox Programm.')
    parser.add_argument(
        'filename',
        default='fotobox.json',
        metavar='c',
        type=str,
        help='path to config file'
    )
    sys.exit(main(config(parser.parse_args().filename)))
