#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import contextlib

import picamera


class Camera:

    def __init__(self, cam, size):
        self._camera = cam
        self._size = size

    def shoot(self, file_mask):
        return self._camera.capture_continuous(file_mask, resize=self._size)

    @contextlib.contextmanager
    def preview(self):
        self._camera.start_preview(hflip=True)
        try:
            yield
        finally:
            self._camera.stop_preview()

    @contextlib.contextmanager
    def overlay(self, image, size, alpha, layer):
        o = self._camera.add_overlay(
            image.tostring(), size=size, alpha=alpha, layer=layer)
        try:
            yield
        finally:
            self._camera.remove_overlay(o)


@contextlib.contextmanager
def context(size):
    with picamera.PiCamera() as cam:
        yield Camera(cam, size)
