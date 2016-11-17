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


def switch_on(port):
    GPIO.output(port, True)


def switch_off(port):
    GPIO.output(port, False)


@contextlib.contextmanager
def flash(lights):
    for light in lights:
        GPIO.output(light, False)
    try:
        yield
    finally:
        for light in lights:
            GPIO.output(light, True)


@contextlib.contextmanager
def context():
    GPIO.setmode(GPIO.BOARD)
    try:
        yield
    finally:
        GPIO.cleanup()
