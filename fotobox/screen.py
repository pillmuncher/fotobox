#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

import contextlib

import pygame


def show_image(image, screen, offset, flip=False):
    if isinstance(image, str):
        image = pygame.image.load(image)
    screen.blit(image, offset)
    if flip:
        pygame.display.flip()


def set_caption(caption):
    pygame.display.set_caption(caption)


def scale_image(image, size):
    return pygame.transform.scale(image, size)


def load_image(file_name):
    return pygame.image.load(file_name)


def play_sound(file_name):
    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play(0)


def stop_sound():
    pygame.mixer.music.stop()


def show_mouse():
    pygame.mouse.set_visible(True)


def hide_mouse():
    pygame.mouse.set_visible(False)


@contextlib.contextmanager
def context(size):
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 1, 1024 * 3)
    try:
        yield pygame.display.set_mode(size, pygame.FULLSCREEN)
    finally:
        pygame.quit()
