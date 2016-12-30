#!/usr/bin/env python
# coding: utf-8

import contextlib
import time

import RPi.GPIO as GPIO

from .util import inject


GPIO.setmode(GPIO.BOARD)
time.sleep(1)


class PushButton:

    def __init__(self, port, bounce_time):
        def handle(port):
            if GPIO.input(port):
                print("\n**************************")
                print("Button(port={0}) losgelassen.".format(port))
                self.released()
            else:
                print("\n**************************")
                print("Button(port={0}) gedrückt.".format(port))
                self.pressed()
        GPIO.setup(port, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            port, GPIO.BOTH, bouncetime=bounce_time, callback=handle)

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
    try:
        yield
    finally:
        GPIO.cleanup()
