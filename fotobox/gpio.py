#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import contextlib

import RPi.GPIO as GPIO


class PushButton:

    def __init__(self, port, bounce_time):
        GPIO.setup(port, GPIO.IN)
        GPIO.add_event_detect(
            port, GPIO.BOTH, bouncetime=bounce_time, callback=self._handle)

    def _handle(self, port):
        if GPIO.input(port):
            self.pressed()
        else:
            self.released()

    def pressed(self):
        pass

    def released(self):
        pass


def setup_out(port):
    GPIO.setup(port, GPIO.OUT)


def set_high(*ports):
    for port in ports:
        GPIO.output(port, True)


def set_low(*ports):
    for port in ports:
        GPIO.output(port, False)


@contextlib.contextmanager
def context():
    GPIO.setmode(GPIO.BOARD)
    try:
        yield
    finally:
        GPIO.cleanup()
