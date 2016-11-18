#!/usr/bin/env python
# coding: utf-8

import contextlib
import pygame


def show_image(image, screen, offset, flip=False):
    screen.blit(image, offset)
    if flip:
        pygame.display.flip()


def set_caption(caption):
    pygame.display.set_caption(caption)


def load_image(file_name):
    return pygame.image.load(file_name)


def play_sound(file_name):
    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play(0)


def stop_sound():
    pygame.mixer.music.stop()


@contextlib.contextmanager
def context(size):
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 1, 1024 * 3)
    pygame.mouse.set_visible(False)
    try:
        yield pygame.display.set_mode(size, pygame.FULLSCREEN)
    finally:
        pygame.mouse.set_visible(True)
        pygame.quit()
