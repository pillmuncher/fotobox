#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import json
import os.path

import PIL.Image

from fotobox import main


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

    def photo_length(total, padding, margin_a, margin_b, parts):
        blank = margin_a + (parts - 1) * padding + margin_b
        return (total - blank) // parts

    def get_box(n):
        row, col = divmod(n, c.montage.cols)
        left = c.montage.margin.left + c.montage.photo.padded_width * col
        right = left + c.montage.photo.width
        upper = c.montage.margin.top + c.montage.photo.padded_height * row
        lower = upper + c.montage.photo.height
        return left, upper, right, lower

    with open(file_name, 'r') as config_file:
        c = Config(json.load(config_file))
    c.photo.size = c.photo.width, c.photo.height
    c.screen.size = c.screen.width, c.screen.height
    c.screen.rect = 0, 0, c.montage.width, c.montage.height
    c.montage.number_of_photos = c.montage.cols * c.montage.rows
    c.montage.photo = Config({})
    c.montage.photo.width = photo_length(
        c.screen.width,
        c.montage.padding,
        c.montage.margin.left,
        c.montage.margin.right,
        c.montage.cols,
    )
    c.montage.photo.height = photo_length(
        c.screen.height,
        c.montage.padding,
        c.montage.margin.top,
        c.montage.margin.bottom,
        c.montage.rows,
    )
    c.montage.photo.size = c.montage.photo.width, c.montage.photo.height
    c.montage.photo.padded_width = c.montage.photo.width + c.montage.padding
    c.montage.photo.padded_height = c.montage.photo.height + c.montage.padding
    c.montage.photo.box = [
        get_box(i) for i in xrange(c.montage.number_of_photos)
    ]
    c.montage.image = PIL.Image.new(
        'RGBA',
        c.screen.size,
        c.montage.background,
    )
    c.montage.full_mask = os.path.join(
        c.montage.path,
        c.montage.mask,
    )
    c.collage.full_mask = os.path.join(
        c.collage.path,
        c.collage.mask,
    )
    c.collage.logo = PIL.Image.open(c.collage.logofile)
    c.photo.file_mask = os.path.join(
        c.photo.path,
        c.photo.mask,
    )
    c.etc.prepare.full_image_mask = os.path.join(
        c.etc.path,
        c.etc.prepare.image_mask,
    )
    c.etc.countdown.full_sound_mask = os.path.join(
        c.etc.path,
        c.etc.countdown.sound_mask,
    )
    c.etc.countdown.full_image_mask = os.path.join(
        c.etc.path,
        c.etc.countdown.image_mask,
    )
    c.etc.smile.full_image_file = os.path.join(
        c.etc.path,
        c.etc.smile.image_file,
    )
    c.etc.black.full_image_file = os.path.join(
        c.etc.path,
        c.etc.black.image_file,
    )
    c.etc.watermark_file = os.path.join(
        c.etc.path,
        c.etc.watermark.image_file,
    )
    c.etc.watermark.image = (
        PIL.Image
        .open(c.etc.watermark_file)
        .resize(c.screen.size)
    )
    c.etc.songs.mask = os.path.join(c.etc.songs.dir, c.etc.songs.sound_mask)
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
