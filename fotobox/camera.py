#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import contextlib

import picamera


class Camera:

    def __init__(self, cam):
        self._camera = cam

    def capture_continuous(self, file_name, resize):
        return self._camera.capture_continuous(file_name, resize=resize)

    @contextlib.contextmanager
    def preview(self, flip=True):
        self._camera.start_preview(hflip=flip)
        try:
            yield
        finally:
            self._camera.stop_preview()

    @contextlib.contextmanager
    def overlay(self, image, size, alpha, layer):
        o = self._camera.add_overlay(image.tostring(), size=size)
        o.alpha = 64
        o.layer = 3
        try:
            yield
        finally:
            self._camera.remove_overlay(o)


@contextlib.contextmanager
def context():
    with picamera.PiCamera() as cam:
        yield Camera(cam)
