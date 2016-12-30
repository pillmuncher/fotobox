#!/usr/bin/env python
# coding: utf-8

import contextlib
import time

import RPi.GPIO as GPIO

from .util import inject

GPIO.setmode(GPIO.BOARD)
time.sleep(1)


class PushButton:

    def __init__(self, port, hold_time, bounce_time):
        def handle(_):
            t = time.time() + hold_time
            while t > time.time():
                time.sleep(.1)
                if GPIO.input(port):
                    self.cancelled()
                    return
            else:
                self.pushed()
        GPIO.setup(port, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            port, GPIO.FALLING, bouncetime=bounce_time, callback=handle)

    def pushed(self):
        pass

    def cancelled(self):
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
    try:
        yield
    finally:
        GPIO.cleanup()
