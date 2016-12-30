#!/usr/bin/env python
# coding: utf-8

import contextlib
import functools
import glob
import os.path
import random
import time
from collections import namedtuple

from PIL import Image
from rx import Observable
from rx.subjects import Subject
from rx.concurrency import EventLoopScheduler, ThreadPoolScheduler

from .camera import context as camera_context
from .display import show_image, load_image, resize_image, play_sound
from .display import context as display_context
from .gpio import PushButton, setup_out, switch_on, switch_off, flash
from .gpio import context as gpio_context
from .util import const, thread_thru, inject


Log = namedtuple("Log", "info")
Shoot = namedtuple("Shoot", "code")
Quit = namedtuple("Quit", "code")
ShowRandomMontage = namedtuple("ShowRandomMontage", "")
Blink = namedtuple("Blink", "")

ButtonPressed = namedtuple("ButtonPressed", "time button")
ButtonReleased = namedtuple("ButtonReleased", "time button")
ButtonPushed = namedtuple("ButtonPushed", "button pressed released")

is_pressed = inject(isinstance, ButtonPressed)
is_released = inject(isinstance, ButtonReleased)
is_pushed = inject(isinstance, ButtonPushed)


@functools.singledispatch
def handle_command(cmd, conf):
    raise NotImplementedError


@handle_command.register(Log)
def handle_log(cmd, conf):
    print(cmd.info)


@handle_command.register(Shoot)
def handle_shoot(cmd, conf):
    with conf.shooting_lock:
        with flash(conf.photo.lights), conf.camera.preview():
            timestamp = time.strftime(conf.photo.time_mask)
            file_names = conf.camera.shoot(
                conf.photo.file_mask.format(timestamp))
            montage = conf.montage.image.copy()
            printout = conf.printout.image.copy()
            for i in conf.photo.range:
                count_down(i + 1, conf)
                photo = Image.open(next(file_names))
                paste_to(montage,
                         photo.convert("RGBA"), i, conf.montage.layout)
                paste_to(printout, photo, i, conf.printout.layout)
                time.sleep(5)
            file_name = conf.montage.file_mask.format(timestamp)
            (Image
             .blend(montage, conf.montage.watermark.image, 0.25)
             .save(file_name))
            show_montage(file_name, conf)
        printout.save(conf.printout.file_mask.format(timestamp))
        time.sleep(conf.montage.interval)


@handle_command.register(Quit)
def handle_quit(cmd, conf):
    conf.exit_code.put(cmd.code)


@handle_command.register(ShowRandomMontage)
def handle_show_montage(cmd, conf):
    if conf.shooting_lock.acquire(blocking=False):
        try:
            thread_thru(conf.montage.glob_mask,
                        glob.glob,
                        random.choice,
                        inject(show_montage, conf))
        finally:
            conf.shooting_lock.release()


@handle_command.register(Blink)
def handle_blink(cmd, conf):
    if conf.shooting_lock.acquire(blocking=False):
        conf.shooting_lock.release()
        blink_once(conf.led.yellow, conf)
    else:
        blink_once(conf.led.red, conf)


def blink_once(led, conf):
    switch_on(led)
    time.sleep(conf.blink.interval / 2)
    switch_off(led)


def lightshow(seconds, conf):
    switch_off(conf.led.green)
    switch_off(conf.led.yellow)
    switch_off(conf.led.red)
    time.sleep(seconds)
    switch_on(conf.led.green)
    time.sleep(seconds)
    switch_on(conf.led.yellow)
    time.sleep(seconds)
    switch_on(conf.led.red)
    switch_off(conf.led.green)
    switch_off(conf.led.yellow)
    switch_off(conf.led.red)


def show_montage(file_name, conf):
    thread_thru(
        file_name,
        load_image,
        inject(resize_image, conf.screen.size),
        # inject(Image.Image.resize, conf.screen.size, Image.ANTIALIAS),
        inject(show_image, conf.display, conf.screen.offset))


def show_overlay(file_name, position, seconds, conf):
    img = Image.open(os.path.join(conf.resource_path, file_name))
    width = ((img.size[0] + 31) // 32) * 32
    height = ((img.size[1] + 15) // 16) * 16
    pad = Image.new("RGB", (width, height))
    pad.paste(img, position)
    with conf.camera.overlay(pad.tostring(), size=img.size, alpha=64, layer=3):
        time.sleep(seconds)


def count_down(number, conf):
    show_overlay(conf.photo.countdown.prepare.image_mask.format(number),
                 conf.photo.countdown.prepare.image_position, 2, conf)
    for i in 3, 2, 1:
        play_sound(conf.photo.countdown.count.sound_mask.format(i))
        show_overlay(conf.photo.countdown.count.image_mask.format(i),
                     conf.photo.countdown.count.image_position, 1, conf)
    show_overlay(conf.photo.countdown.smile.image_file,
                 conf.photo.countdown.smile.image_position, 1.5, conf)
    if conf.photo.countdown.songs.enabled:
        thread_thru(conf.photo.countdown.songs.glob_mask,
                    glob.glob, random.choice, play_sound)


def detect_push(previous, current):
    if is_pressed(previous) and is_released(current):
        return ButtonPushed(button=previous.button,
                            pressed=previous.time,
                            released=current.time)
    else:
        return current


def non_overlapping(previous, current):
    # assert previous.pressed <= current.pressed
    if previous.released <= current.pressed:
        return current
    else:
        return previous


def to_command(pushed):
    if pushed.button.hold >= pushed.released - pushed.pressed:
        return pushed.button.command
    else:
        return pushed.button.log


def paste_to(image, photo, i, layout):
    image.paste(photo.resize(layout.size, Image.ANTIALIAS), layout.box[i])


class Button(PushButton):

    def __init__(self, command, event, bounce_time, scheduler):
        super().__init__(event.port, bounce_time)
        self.hold = event.hold
        self.command = command(code=event.code)
        self.log = Log(info=event.info)
        self.events = Subject()
        self.pushes = (self
                       .events
                       .observe_on(scheduler)
                       .scan(detect_push)
                       .where(is_pushed)
                       .distinct_until_changed())

    def pressed(self):
        self.events.on_next(ButtonPressed(time=time.time(), button=self))

    def released(self):
        self.events.on_next(ButtonReleased(time=time.time(), button=self))


@contextlib.contextmanager
def bus_context(conf):
    bus = Subject()
    blinker_ticks = Observable.interval(conf.blink.interval * 1000)
    montage_ticks = Observable.interval(conf.montage.interval * 1000)
    # event_loop = EventLoopScheduler()
    # buttons = [Button(Shoot, conf.event.shoot, conf.bounce_time, event_loop),
               # Button(Quit, conf.event.quit, conf.bounce_time, event_loop),
               # Button(Quit, conf.event.reboot, conf.bounce_time, event_loop),
               # Button(Quit, conf.event.shutdown, conf.bounce_time, event_loop)]
    commands = (Observable
                # .merge([button.pushes for button in buttons])
                # .scan(non_overlapping)
                      # seed=ButtonPushed(button=None, pressed=0, released=0))
                # .distinct_until_changed()
                # .map(to_command)
                .merge(ThreadPoolScheduler(max_workers=conf.workers),
                       blinker_ticks.map(const(Blink())),
                       montage_ticks.map(const(ShowRandomMontage())),
                       bus))
    with commands.subscribe(on_next=inject(handle_command, conf)):
        yield bus


def run(conf):
    with gpio_context():
        for light in conf.photo.lights:
            setup_out(light)
        setup_out(conf.led.red)
        setup_out(conf.led.yellow)
        setup_out(conf.led.green)
        switch_on(conf.led.green)
        with display_context(size=conf.screen.size) as conf.display:
            with camera_context(size=conf.photo.size) as conf.camera:
                with bus_context(conf) as conf.bus:
                    try:
                        result = conf.exit_code.get()
                        print("\n**************************\n")
                        print(result)
                        print("\n**************************\n")
                        # return result
                    finally:
                        lightshow(1, conf)
