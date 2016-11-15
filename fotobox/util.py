#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

from functools import reduce


def const(x):
    def ignore(*args, **kwargs):
        return x
    return ignore


def flip(f):
    def flipped(*args):
        return f(*reversed(args))
    return flipped


def apply(f, *args, **kwargs):
    return f(*args, **kwargs)


rapply = flip(apply)


def thread_thru(v, *fs):
    return reduce(rapply, fs, v)


def inject(f, *args, **kwargs):
    def inj(x):
        return f(x, *args, **kwargs)
    return inj
