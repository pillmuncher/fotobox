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

    def side_length(total, padding, margin_a, margin_b):
        return (total - (margin_a + padding + margin_b)) // 2

    def get_box(n, pad_width, pad_height, target):
        col, row = divmod(n, 2)
        pad_width = target.photo.width + target.margin.padding
        pad_height = target.photo.height + target.margin.padding
        left = target.margin.left + pad_width * col
        right = left + target.photo.width
        upper = target.margin.top + pad_height * row
        lower = upper + target.photo.height
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
    c.montage.photo.width = side_length(
        c.screen.width,
        c.montage.margin.padding,
        c.montage.margin.left,
        c.montage.margin.right,
    )
    c.montage.photo.height = side_length(
        c.screen.height,
        c.montage.margin.padding,
        c.montage.margin.top,
        c.montage.margin.bottom,
    )
    pad_width = c.montage.layout.width + c.montage.margin.padding
    pad_height = c.montage.layout.height + c.montage.margin.padding
    c.montage.layout.size = c.montage.layout.width, c.montage.layout.height
    c.montage.layout.box = [
        get_box(i, pad_width, pad_height, c.montage) for i in c.photo.range
    ]
    c.montage.image = Image.new('RGBA', c.screen.size, c.montage.background)
    c.montage.watermark.image = (
        Image
        .open(c.montage.watermark.image_file)
        .resize(c.screen.size, Image.ANTIALIAS)
    )
    c.montage.glob_mask = c.montage.file_mask.format('*')
    c.printout.image = Image.open(c.printout.image_file)
    c.printout.layout = Config({})
    c.printout.layout.width, c.printout.layout.height = c.printout.image.size
    pad_width = c.printout.layout.width + c.printout.margin.padding
    pad_height = c.printout.layout.height + c.printout.margin.padding
    c.printout.layout.box = [
        get_box(i, pad_width, pad_height, c.printout) for i in c.photo.range
    ]
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
