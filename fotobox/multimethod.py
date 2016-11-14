#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, absolute_import, division

from functools import wraps
from inspect import signature, Signature


_REGISTRY = {}


class MultiMethod(object):

    def __init__(self, name):
        self.name = name
        self.typemap = []

    def __call__(self, *args):
        for types, function in self.typemap:
            args_are_matching = (isinstance(a, t) for a, t in zip(args, types))
            if len(args) == len(types) and all(args_are_matching):
                return function(*args)
        raise TypeError("no match")

    def register(self, types, function):
        self.typemap.append((types, function))


def multimethod(function):
    name = function.__name__
    mm = _REGISTRY.get(name)
    if mm is None:
        mm = _REGISTRY[name] = MultiMethod(name)
    types = tuple(
        object if each.annotation is Signature.empty else each.annotation
        for each in signature(function).parameters.values())
    mm.register(types, function)

    @wraps(function)
    def wrapper(*args, **kwargs):
        return mm(*args, **kwargs)
    return wrapper
