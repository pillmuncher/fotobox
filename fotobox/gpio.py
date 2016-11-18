#!/usr/bin/env python
# coding: utf-8

import contextlib
import RPi.GPIO as GPIO
from .util import inject


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


setup_out = inject(GPIO.setup, GPIO.OUT)
switch_on = inject(GPIO.output, True)
switch_off = inject(GPIO.output, False)


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
