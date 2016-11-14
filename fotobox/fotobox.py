#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import glob
import os.path
import queue
import random
import time

import picamera
import PIL.Image
import pygame
import RPi.GPIO as GPIO

from collections import namedtuple
from functools import partial, singledispatch

from rx import Observable
from rx.subjects import Subject
from rx.concurrency import EventLoopScheduler, ThreadPoolScheduler


def flip(f):
    def flipped(*args):
        return f(*reversed(args))
    return flipped


def switch_on(pin):
    GPIO.output(pin, True)


def switch_off(pin):
    GPIO.output(pin, False)


def lights_on(pins):
    for pin in pins:
        GPIO.output(pin, False)


def lights_off(pins):
    for pin in pins:
        GPIO.output(pin, True)


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


def show_image(image, conf):
    conf.screen.blit(image, conf.screen.offset)
    pygame.display.flip()


def play_sound(file_name):
    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play(0)


def stop_sound():
    pygame.mixer.music.stop()


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


ButtonPressed = namedtuple('ButtonPressed', 'port hold time')
ButtonReleased = namedtuple('ButtonReleased', 'port time')
ButtonPushed = namedtuple('ButtonPushed', 'port duration pressed released')

is_pressed = partial(flip(isinstance), ButtonPressed)
is_released = partial(flip(isinstance), ButtonReleased)
is_pushed = partial(flip(isinstance), ButtonPushed)

Log = namedtuple('Log', 'text')
Shoot = namedtuple('Shoot', '')
Reset = namedtuple('Reset', '')
Quit = namedtuple('Quit', '')
Reboot = namedtuple('Reboot', '')
Shutdown = namedtuple('Shutdown', '')
CreateCollage = namedtuple('CreateCollage', 'imgs time')
ShowRandomMontage = namedtuple('ShowRandomMontage', 'num')
Blink = namedtuple('Blink', 'num')


@singledispatch
def handle_command(cmd, conf):
    pass


@handle_command.register(Log)
def handle_log(cmd, conf):
    print(cmd.text)


@handle_command.register(Shoot)
def handle_shoot(cmd, conf):
    timestamp = time.strftime(conf.photo.time_mask)
    photo_file_mask = conf.photo.file_mask.format(timestamp)
    photo_file_names = conf.camera.capture_continuous(
        photo_file_mask,
        resize=conf.photo.size,
    )
    montage = conf.montage.image.copy()
    imgs = []
    conf.led.status = conf.led.red
    lights_on(conf.photo.lights)
    conf.camera.start_preview(hflip=True)
    for i in xrange(conf.montage.number_of_photos):
        count_down(i + 1, conf)
        photo_file_name = next(photo_file_names)
        imgs.append(PIL.Image.open(photo_file_name))
        montage.paste(
            PIL.Image
            .open(photo_file_name)
            .convert('RGBA')
            .resize(conf.montage.photo.size),
            conf.montage.photo.box[i],
        )
        time.sleep(5.0)
    conf.camera.stop_preview()
    lights_off(conf.photo.lights)
    conf.led.status = conf.led.yellow
    show_image(pygame.image.load(conf.etc.black.full_image_file), conf)
    montage_file_name = conf.montage.full_mask.format(timestamp)
    (PIL.Image
        .blend(montage, conf.etc.watermark.image, .25)
        .save(montage_file_name))
    show_image(pygame.image.load(montage_file_name), conf)
    conf.bus.on_next(CreateCollage(imgs, timestamp))
    time.sleep(conf.montage.interval)


@handle_command.register(Reset)
def handle_reset(cmd, conf):
    pass


@handle_command.register(Quit)
def handle_quit(cmd, conf):
    conf.exit_code.put(conf.event.quit.code)


@handle_command.register(Reboot)
def handle_reboot(cmd, conf):
    conf.exit_code.put(conf.event.reboot.code)


@handle_command.register(Shutdown)
def handle_shut_down(cmd, conf):
    conf.exit_code.put(conf.event.shutdown.code)


@handle_command.register(CreateCollage)
def handle_create_collage(cmd, conf):
    collage = make_collage(
        conf.collage.margin,
        conf.collage.background,
        *cmd.imgs)
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
    file_mask = conf.montage.full_mask.format('*')
    file_names = glob.glob(file_mask)
    file_name = random.choice(file_names)
    image = pygame.image.load(file_name)
    show_image(pygame.transform.scale(image, conf.screen.size), conf)


@handle_command.register(Blink)
def handle_blink(cmd, conf):
    if cmd.num % 2:
        switch_on(conf.led.status)
    else:
        switch_off(conf.led.status)


class Button(Subject):

    def __init__(self, port, hold, bounce_time):
        super(Button, self).__init__()
        self._port = port
        self._hold = hold
        GPIO.setup(port, GPIO.IN)
        GPIO.add_event_detect(
            port,
            GPIO.BOTH,
            bouncetime=bounce_time,
            callback=self._handle)

    def _handle(self, port):
        if GPIO.input(port):
            self.on_next(ButtonPressed(port, self._hold, time.time()))
        else:
            self.on_next(ButtonReleased(port, time.time()))

    def dispose(self):
        GPIO.remove_event_detect(self._port)
        super(Button, self).dispose()


def detect_push(prev, curr):
    assert prev.time <= curr.time
    if is_pressed(prev) and is_released(curr):
        return ButtonPushed(prev.port, prev.hold, prev.time, curr.time)
    else:
        return curr


def non_overlapping(prev, curr):
    assert prev.pressed <= curr.pressed
    if prev.released <= curr.pressed:
        return curr
    else:
        return prev


def to_command(pushed, conf):
    command, info = conf.port_data[pushed.port]
    if pushed.duration >= pushed.released - pushed.pressed:
        return command
    else:
        return info


def make_button(event, bounce_time, scheduler):
    return (
        Observable
        .using(scheduler, Button(event.port, event.hold, bounce_time))
        .scan(detect_push)
        .where(is_pushed)
        .distinct_until_changed()
    )


def main(conf):
    conf.led.status = conf.led.yellow
    conf.camera = picamera.PiCamera()
    conf.camera.capture('/dev/null', 'png')
    pygame.init()
    conf.screen = pygame.display.set_mode(
        conf.screen.size,
        pygame.FULLSCREEN,
    )
    pygame.display.set_caption('Photo Booth Pics')
    pygame.mouse.set_visible(False)
    pygame.mixer.pre_init(44100, -16, 1, 1024 * 3)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(conf.led.green, GPIO.OUT)
    GPIO.setup(conf.led.yellow, GPIO.OUT)
    GPIO.setup(conf.led.red, GPIO.OUT)
    for light in conf.photo.lights:
        GPIO.setup(light, GPIO.OUT)
    switch_on(conf.led.green)
    conf.exit_code = queue.Queue(maxsize=1)
    conf.port_data = {
        conf.event.shoot.port: (Shoot(), Log(conf.event.shoot.info)),
        conf.event.reset.port: (Reset(), Log(conf.event.reset.info)),
        conf.event.quit.port: (Quit(), Log(conf.event.quit.info)),
        conf.event.reboot.port: (Reboot(), Log(conf.event.reboot.info)),
        conf.event.shutdown.port: (Shutdown(), Log(conf.event.shutdown.info)),
    }
    sched = EventLoopScheduler()
    buttons = [
        make_button(conf.event.shoot, conf.etc.bounce_time, sched),
        make_button(conf.event.reset, conf.etc.bounce_time, sched),
        make_button(conf.event.quit, conf.etc.bounce_time, sched),
        make_button(conf.event.reboot, conf.etc.bounce_time, sched),
        make_button(conf.event.shutdown, conf.etc.bounce_time, sched),
    ]
    conf.bus = Subject()
    montage = Observable.interval(conf.montage.interval).map(ShowRandomMontage)
    blinking = Observable.interval(conf.blink.interval).map(Blink)
    (
        Observable
        .merge(*buttons)
        .scan(non_overlapping, seed=ButtonPushed(None, None, 0, 0))
        .distinct_until_changed()
        .map(partial(flip(to_command), conf))
        .merge(
            ThreadPoolScheduler(max_workers=conf.etc.workers),
            montage, blinking, conf.bus)
        .subscribe(on_next=partial(flip(handle_command), conf))
    )
    try:
        return conf.exit_code.get()
    finally:
        blinking.dispose()
        montage.dispose()
        conf.bus.dispose()
        for each in buttons:
            each.dispose()
        conf.led.status = None
        lightshow(1, conf)
        time.sleep(3)
        GPIO.cleanup()
        pygame.mouse.set_visible(True)
        pygame.quit()
        conf.camera.close()
