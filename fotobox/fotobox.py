#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

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
from .display import show_image, load_image, play_sound, context as ui_context
from .gpio import PushButton, setup_out, switch_on, switch_off, flash
from .gpio import context as gpio_context
from .util import const, thread_thru, inject


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


def show_overlay(file_name, position, seconds, conf):
    img = Image.open(os.path.join(conf.etc.path, file_name))
    pad = Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
    ))
    pad.paste(img, position)
    with conf.camera.overlay(pad.tostring(), size=img.size, alpha=64, layer=3):
        time.sleep(seconds)


def count_down(n, conf):
    show_overlay(
        conf.etc.prepare.full_image_mask.format(n),
        conf.etc.prepare.image_position,
        2,
        conf,
    )
    for i in (3, 2, 1):
        play_sound(conf.etc.countdown.full_sound_mask.format(i))
        show_overlay(
            conf.etc.countdown.full_image_mask.format(i),
            conf.etc.countdown.image_position,
            1,
            conf,
        )
    if conf.etc.songs.enabled:
        thread_thru(conf.etc.songs.mask, glob.glob, random.choice, play_sound)
    show_overlay(
        conf.etc.smile.full_image_file,
        conf.etc.smile.image_position,
        1.5,
        conf,
    )


def make_collage(margin, background, img11, img12, img21, img22):
    assert img11.size == img21.size == img21.size == img22.size
    img_width, img_height = img11.size
    width = img_width * 2 + margin.padding + margin.left + margin.right
    height = img_height * 2 + margin.padding + margin.top + margin.bottom
    horizontal, vertical = width * 3, height * 4
    if horizontal < vertical:
        original_width = width
        width *= vertical
        width /= horizontal
        left1 = margin.left + (width - original_width) / 2
        top1 = margin.top
    elif horizontal > vertical:
        original_height = height
        height *= horizontal
        height /= vertical
        left1 = margin.left
        top1 = margin.top + (height - original_height) / 2
    else:
        left1 = margin.left
        top1 = margin.top
    left2 = left1 + img_width + margin.padding
    top2 = top1 + img_height + margin.padding
    collage = Image.new('RGB', (int(width), int(height)), background)
    collage.paste(img11, (int(left1), int(top1)))
    collage.paste(img12, (int(left2), int(top1)))
    collage.paste(img21, (int(left1), int(top2)))
    collage.paste(img22, (int(left2), int(top2)))
    return collage


ButtonPressed = namedtuple('ButtonPressed', 'time command')
ButtonReleased = namedtuple('ButtonReleased', 'time')
ButtonPushed = namedtuple('ButtonPushed', 'command log pressed released')

is_pressed = inject(isinstance, ButtonPressed)
is_released = inject(isinstance, ButtonReleased)
is_pushed = inject(isinstance, ButtonPushed)

Log = namedtuple('Log', 'text')
Shoot = namedtuple('Shoot', 'event')
Quit = namedtuple('Quit', 'event')
CreateCollage = namedtuple('CreateCollage', 'photos time')
ShowRandomMontage = namedtuple('ShowRandomMontage', '')
Blink = namedtuple('Blink', '')


@functools.singledispatch
def handle_command(cmd, conf):
    raise NotImplementedError


@handle_command.register(Log)
def handle_log(cmd, conf):
    print(cmd.text)


@handle_command.register(Shoot)
def handle_shoot(cmd, conf):
    with conf.shooting_lock, flash(conf.photo.lights), conf.camera.preview():
        timestamp = time.strftime(conf.photo.time_mask)
        file_names = conf.camera.shoot_photos(
            conf.photo.file_mask.format(timestamp),
        )
        photos = []
        montage = conf.montage.image.copy()
        for i in xrange(conf.montage.number_of_photos):
            count_down(i + 1, conf)
            photo = Image.open(next(file_names))
            photos.append(photo)
            montage.paste(
                photo
                .copy()
                .convert('RGBA')
                .resize(conf.montage.photo.size, Image.ANTIALIAS),
                conf.montage.photo.box[i],
            )
            time.sleep(5)
        montage = Image.blend(montage, conf.etc.watermark.image, .25)
        montage.save(conf.montage.full_mask.format(timestamp))
        show_image(montage, conf.display, conf.screen.offset, flip=True)
        conf.bus.on_next(CreateCollage(photos, timestamp))
        time.sleep(conf.montage.interval)


@handle_command.register(Quit)
def handle_quit(cmd, conf):
    conf.exit_code.put(cmd.event.code)


@handle_command.register(CreateCollage)
def handle_create_collage(cmd, conf):
    collage = make_collage(
        conf.collage.margin, conf.collage.background, *cmd.photos)
    width, height = collage.size
    size = int(height * 1.5), height
    printout = Image.new('RGB', size, conf.collage.background)
    printout.paste(collage, (0, 0))
    printout.paste(conf.collage.logo, (width, 0))
    printout.save(conf.collage.full_mask.format(cmd.time))


@handle_command.register(ShowRandomMontage)
def handle_show_random_montage(cmd, conf):
    if conf.shooting_lock.acquire(blocking=False):
        try:
            thread_thru(
                '*',
                conf.montage.full_mask.format,
                glob.glob,
                random.choice,
                load_image,
                lambda img: img.resize(conf.screen.size, Image.ANTIALIAS),
                inject(show_image, conf.display, conf.screen.offset),
            )
        finally:
            conf.shooting_lock.release()


@handle_command.register(Blink)
def handle_blink(cmd, conf):
    if conf.shooting_lock.acquire(blocking=False):
        conf.shooting_lock.release()
        blink_once(conf.led.yellow, conf)
    else:
        blink_once(conf.led.red, conf)


def detect_push(prev, curr):
    assert prev.time <= curr.time
    if is_pressed(prev) and is_released(curr):
        return ButtonPushed(prev.command, prev.log, prev.time, curr.time)
    else:
        return curr


def non_overlapping(prev, curr):
    assert prev.pressed <= curr.pressed
    if prev.released <= curr.pressed:
        return curr
    else:
        return prev


def to_command(pushed):
    if pushed.command.event.hold >= pushed.released - pushed.pressed:
        return pushed.command
    else:
        return pushed.log


class Button(PushButton):

    def __init__(self, command, bounce_time, scheduler):
        self.command = command
        self.log = Log(command.event.info)
        self.events = Subject()
        self.pushes = (
            self
            .events
            .observe_on(scheduler)
            .scan(detect_push)
            .where(is_pushed)
            .distinct_until_changed()
        )
        PushButton.__init__(self, command.port, bounce_time)

    def pressed(self):
        self.events.on_next(ButtonPressed(time.time(), self.command))

    def released(self):
        self.events.on_next(ButtonReleased(time.time()))


@contextlib.contextmanager
def bus_context(conf):
    make_button = inject(Button, conf.etc.bounce_time, EventLoopScheduler())
    buttons = (
        make_button(Shoot(conf.event.shoot)),
        make_button(Quit(conf.event.quit)),
        make_button(Quit(conf.event.reboot)),
        make_button(Quit(conf.event.shutdown)),
    )
    bus = Subject()
    blinker_ticks = Observable.interval(conf.blink.interval)
    montage_ticks = Observable.interval(conf.montage.interval)
    handler = (
        Observable
        .merge([button.pushes for button in buttons])
        .scan(non_overlapping, seed=ButtonPushed(None, None, 0, 0))
        .distinct_until_changed()
        .map(to_command)
        .merge(
            ThreadPoolScheduler(max_workers=conf.etc.workers),
            bus,
            blinker_ticks.map(const(Blink())),
            montage_ticks.map(const(ShowRandomMontage())),
        )
        .subscribe(on_next=inject(handle_command, conf))
    )
    try:
        yield bus
    finally:
        handler.dispose()
        montage_ticks.dispose()
        blinker_ticks.dispose()
        bus.dispose()
        for button in buttons:
            button.events.dispose()


def main(conf):
    with gpio_context():
        for light in conf.photo.lights:
            setup_out(light)
        setup_out(conf.led.red)
        setup_out(conf.led.yellow)
        setup_out(conf.led.green)
        switch_on(conf.led.green)
        with ui_context(size=conf.screen.size) as conf.display:
            with camera_context(size=conf.photo.size) as conf.camera:
                with bus_context(conf) as conf.bus:
                    try:
                        return conf.exit_code.get()
                    finally:
                        lightshow(1, conf)
