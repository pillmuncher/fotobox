#!/usr/bin/env python3
# coding: utf-8

from setuptools import setup, find_packages

setup(
    name="fotobox",
    version="0.2a0",
    packages=find_packages(),
    install_requires=[
        'picamera>=1.12',
        'Pillow>=3.4.2',
        'pygame>=1.9.2b8',
        'fakeRPiGPIO>=0.3a0',
        'Rx>=1.5.3',
    ]
)
