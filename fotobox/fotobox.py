#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import contextlib
import functools
import glob
import os.path
import random
import time

import picamera
import PIL.Image
import pygame
import RPi.GPIO as GPIO

from collections import namedtuple

from rx import Observable
from rx.subjects import Subject
from rx.concurrency import EventLoopScheduler, ThreadPoolScheduler

from util import const, thread_thru, inject


switch = GPIO.output
switch_on = inject(switch, True)
switch_off = inject(switch, False)


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
    time.sleep(seconds)
    switch_off(conf.led.green)
    switch_off(conf.led.yellow)
    switch_off(conf.led.red)


def lights_on(pins):
    for pin in pins:
        GPIO.output(pin, False)


def lights_off(pins):
    for pin in pins:
        GPIO.output(pin, True)


def show_image(image, conf):
    conf.screen.blit(image, conf.screen.offset)
    pygame.display.flip()


def show_overlay(file_name, position, seconds, conf):
    img = PIL.Image.open(os.path.join(conf.etc.path, file_name))
    pad = PIL.Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
    ))
    pad.paste(img, position)
    overlay = conf.camera.add_overlay(pad.tostring(), size=img.size)
    overlay.alpha = 64
    overlay.layer = 3
    time.sleep(seconds)
    conf.camera.remove_overlay(overlay)


def count_down(n, conf):
    show_overlay(
        conf.etc.prepare.full_image_mask.format(n),
        conf.etc.prepare.image_position,
        2,
        conf,
    )
    for i in [3, 2, 1]:
        play_sound(conf.etc.countdown.full_sound_mask.format(i))
        show_overlay(
            conf.etc.countdown.full_image_mask.format(i),
            conf.etc.countdown.image_position,
            1,
            conf,
        )
    if conf.etc.songs.enabled:
        file_names = glob.glob(conf.etc.songs.mask)
        file_name = random.choice(file_names)
        play_sound(file_name)
    show_overlay(
        conf.etc.smile.full_image_file,
        conf.etc.smile.image_position,
        1.5,
        conf,
    )


def play_sound(file_name):
    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play(0)


def stop_sound():
    pygame.mixer.music.stop()


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
    collage = PIL.Image.new('RGB', (int(width), int(height)), background)
    collage.paste(img11, (int(left1), int(top1)))
    collage.paste(img12, (int(left2), int(top1)))
    collage.paste(img21, (int(left1), int(top2)))
    collage.paste(img22, (int(left2), int(top2)))
    return collage


ButtonPressed = namedtuple('ButtonPressed', 'time command')
ButtonReleased = namedtuple('ButtonReleased', 'time')
ButtonPushed = namedtuple('ButtonPushed', 'command pressed released')

is_pressed = inject(isinstance, ButtonPressed)
is_released = inject(isinstance, ButtonReleased)
is_pushed = inject(isinstance, ButtonPushed)

Log = namedtuple('Log', 'text')
Shoot = namedtuple('Shoot', 'event')
Quit = namedtuple('Quit', 'event')
CreateCollage = namedtuple('CreateCollage', 'photos time')
ShowRandomMontage = namedtuple('ShowRandomMontage', '')
Blink = namedtuple('Blink', 'mode')


@functools.singledispatch
def handle_command(cmd, conf):
    raise NotImplementedError


@handle_command.register(Log)
def handle_log(cmd, conf):
    print(cmd.text)


@handle_command.register(Shoot)
def handle_shoot(cmd, conf):
    with conf.lock:
        conf.led.status = conf.led.red
        photos = []
        montage = conf.montage.image.copy()
        lights_on(conf.photo.lights)
        timestamp = time.strftime(conf.photo.time_mask)
        photo_file_names = conf.camera.capture_continuous(
            conf.photo.file_mask.format(timestamp),
            resize=conf.photo.size,
        )
        conf.camera.start_preview(hflip=True)
        for i in xrange(conf.montage.number_of_photos):
            count_down(i + 1, conf)
            photo = PIL.Image.open(next(photo_file_names))
            photos.append(photo)
            montage.paste(
                photo
                .copy()
                .convert('RGBA')
                .resize(conf.montage.photo.size, PIL.Image.ANTIALIAS),
                conf.montage.photo.box[i],
            )
            time.sleep(5.0)
        conf.bus.on_next(CreateCollage(photos, timestamp))
        montage_file_name = conf.montage.full_mask.format(timestamp)
        (PIL.Image
            .blend(montage, conf.etc.watermark.image, .25)
            .save(montage_file_name))
        show_image(pygame.image.load(montage_file_name), conf)
        conf.camera.stop_preview()
        lights_off(conf.photo.lights)
        conf.led.status = conf.led.yellow
        time.sleep(conf.montage.interval)


@handle_command.register(Quit)
def handle_quit(cmd, conf):
    conf.exit_code.put(cmd.event.code)


@handle_command.register(CreateCollage)
def handle_create_collage(cmd, conf):
    collage = make_collage(
        conf.collage.margin,
        conf.collage.background,
        *cmd.photos)
    width, height = collage.size
    printout = PIL.Image.new(
        'RGB',
        (int(height * 1.5), height),
        conf.collage.background)
    printout.paste(collage, (0, 0))
    printout.paste(conf.collage.logo, (width, 0))
    printout.save(conf.collage.full_mask.format(cmd.time))


@handle_command.register(ShowRandomMontage)
def handle_show_random_montage(cmd, conf):
    if conf.lock.acquire(blocking=False):
        try:
            thread_thru(
                '*',
                conf.montage.full_mask.format,
                glob.glob,
                random.choice,
                pygame.image.load,
                inject(pygame.transform.scale, conf.screen.size),
                inject(show_image, conf),
            )
        finally:
            conf.lock.release()


@handle_command.register(Blink)
def handle_blink(cmd, conf):
    switch(conf.led.status, cmd.mode)


def make_blink(n):
    return Blink(n % 2 == 0)


def detect_push(prev, curr):
    assert prev.time <= curr.time
    if is_pressed(prev) and is_released(curr):
        return ButtonPushed(prev.command, prev.time, curr.time)
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
        return Log(pushed.command.event.info)


class Button(Subject):

    def __init__(self, command, bounce_time, scheduler):
        Subject.__init__(self)
        self._command = command
        self.pushes = (
            self
            .observe_on(scheduler)
            .scan(detect_push)
            .where(is_pushed)
            .distinct_until_changed()
        )
        GPIO.setup(command.event.port, GPIO.IN)
        GPIO.add_event_detect(
            command.event.port,
            GPIO.BOTH,
            bouncetime=bounce_time,
            callback=self._handle)

    def _handle(self, port):
        if GPIO.input(port):
            self.on_next(ButtonPressed(time.time(), self._command))
        else:
            self.on_next(ButtonReleased(time.time()))

    def dispose(self):
        GPIO.remove_command_detect(self._command.event.port)
        Subject.dispose(self)


@contextlib.contextmanager
def _gpio(conf):
    GPIO.setmode(GPIO.BOARD)
    try:
        GPIO.setup(conf.led.green, GPIO.OUT)
        GPIO.setup(conf.led.yellow, GPIO.OUT)
        GPIO.setup(conf.led.red, GPIO.OUT)
        for light in conf.photo.lights:
            GPIO.setup(light, GPIO.OUT)
        switch_on(conf.led.green)
        yield
        lightshow(1, conf)
    finally:
        GPIO.cleanup()


@contextlib.contextmanager
def _pygame(conf):
    pygame.init()
    try:
        conf.screen = pygame.display.set_mode(
            conf.screen.size, pygame.FULLSCREEN)
        pygame.display.set_caption('Photo Booth Pics')
        pygame.mouse.set_visible(False)
        pygame.mixer.pre_init(44100, -16, 1, 1024 * 3)
        yield
    finally:
        pygame.mouse.set_visible(True)
        pygame.quit()


@contextlib.contextmanager
def _picamera(conf):
    with picamera.PiCamera() as conf.camera:
        conf.camera.capture('/dev/null', 'png')
        yield


@contextlib.contextmanager
def _rx(conf):
    make_button = inject(Button, conf.etc.bounce_time, EventLoopScheduler())
    buttons = (
        make_button(Shoot(conf.event.shoot)),
        make_button(Quit(conf.event.quit)),
        make_button(Quit(conf.event.reboot)),
        make_button(Quit(conf.event.shutdown)),
    )
    conf.bus = Subject()
    montage_ticks = Observable.interval(conf.montage.interval)
    blinker_ticks = Observable.interval(conf.blink.interval)
    handler = (
        Observable
        .merge([button.pushes for button in buttons])
        .scan(non_overlapping, seed=ButtonPushed(None, None, 0, 0))
        .distinct_until_changed()
        .map(to_command)
        .merge(
            ThreadPoolScheduler(max_workers=conf.etc.workers),
            conf.bus,
            montage_ticks.map(const(ShowRandomMontage())),
            blinker_ticks.map(make_blink))
        .subscribe(on_next=inject(handle_command, conf)))
    try:
        yield
    finally:
        handler.dispose()
        blinker_ticks.dispose()
        montage_ticks.dispose()
        conf.bus.dispose()
        for button in buttons:
            button.dispose()


def main(conf):
    with _gpio(conf), _pygame(conf), _picamera(conf), _rx(conf):
        return conf.exit_code.get()
