#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (c) 2014 Ben Ockmore
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""setup.py script for waveplot-scanner."""

from distutils.core import setup

setup(
    name='waveplot-scanner',
    version='0.0.1',
    description='Tool to scan audio files, and generate and upload WavePlots.',
    long_description="""WavePlot is a system for storing data about audio
    files. Audio files can be scanned using this python script on any system
    with libwaveplot installed, and the generated WavePlots will be uploaded
    to a central server at http://waveplot.net for public viewing.

    In the future, this package may be renamed and additional functionality
    included, such as matching previously untagged files and tagging those
    files with metadata.

    This script is mainly intended to demonstrate how other applications might
    use the libwaveplot library to make use of the WavePlot system themselves.
    """,
    author='Ben Ockmore',
    author_email='ben.sput@gmail.com',
    url='http://waveplot.net',
    py_modules=['waveplot'],
    requires=[
        'requests (>=2.4.0)',
    ],
    scripts=['waveplot-scanner.py'],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows :: Windows 7',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Multimedia :: Sound/Audio :: Analysis',
    ]
)
