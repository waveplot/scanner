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

"""Provides helper classes and functions for retrieving and storing WavePlot
data on the WavePlot server, at http://waveplot.net."""

from __future__ import print_function

import os
import requests
import base64
import json
import zlib
import simplejson
import sys

from ctypes import Structure, c_char_p, c_uint32, c_uint8, c_uint16, POINTER, \
    c_float, c_size_t, cdll

THUMB_IMAGE_WIDTH = 50
THUMB_IMAGE_HEIGHT = 21

PREVIEW_IMAGE_WIDTH = 400
PREVIEW_IMAGE_HEIGHT = 151

SERVER = b'http://waveplot.net'


class _File(Structure):
    _fields_ = [("path", c_char_p)]
    # Other fields are meaningless to Python (libav stuff)


class _Info(Structure):
    _fields_ = [
        ("duration_secs", c_uint32),
        ("num_channels", c_uint8),
        ("bit_depth", c_uint16),
        ("bit_rate", c_uint32),
        ("sample_rate", c_uint32),
        ("file_format", c_char_p)
    ]


class _AudioSamples(Structure):
    _fields_ = [
        ("samples", POINTER(POINTER(c_float))),
        ("num_channels", c_size_t),
        ("length", c_size_t)
    ]


class _DR(Structure):
    _fields_ = [
        ("channel_peak", POINTER(POINTER(c_float))),
        ("channel_rms", POINTER(POINTER(c_float))),
        ("num_channels", c_size_t),
        ("length", c_size_t),
        ("rating", c_float),
        ("capacity", c_size_t),
        ("processed_samples", c_size_t)
    ]


class _WavePlot(Structure):
    _fields_ = [
        ("values", POINTER(c_float)),
        ("resample", POINTER(c_float)),
        ("length", c_size_t),
        ("capacity", c_size_t)
    ]


class WavePlot(object):
    lib = None

    def __init__(self, *args, **kwargs):
        super(WavePlot, self).__init__(*args, **kwargs)

        if self.lib is None:
            WavePlot._init_libwaveplot()

        self.uuid = None
        self.length = None
        self.trimmed_length = None

        self.dr_level = None

        self.source_type = None
        self.sample_rate = None
        self.bit_depth = None
        self.bit_rate = None

        self.num_channels = None

        self.image_sha1 = None
        self.thumbnail = None
        self.sonic_hash = None

        self.version = None

        self.data = None

        self.path = None

    @classmethod
    def _init_libwaveplot(cls):
        """ Initializes the libwaveplot library, which should have been
        installed on this machine along with python-waveplot. If not, raise an
        Exception to show that the library wasn't found and the installation is
        bad. """

        if sys.platform.startswith('win32'):
            cls.lib = cdll.LoadLibrary("libwaveplot-0.dll")
        else:
            cls.lib = cdll.LoadLibrary("libwaveplot.so.0")

        cls.lib.init()
        cls.lib.alloc_file.restype = POINTER(_File)
        cls.lib.alloc_info.restype = POINTER(_Info)
        cls.lib.alloc_audio_samples.restype = POINTER(_AudioSamples)
        cls.lib.alloc_waveplot.restype = POINTER(_WavePlot)
        cls.lib.alloc_dr.restype = POINTER(_DR)
        cls.lib.version.restype = c_char_p

    def _get_waveplot_ptr(self):
        w_ptr = self.lib.alloc_waveplot()

        scaled_data = [float(x)/200.0 for x in bytearray(self.data)]

        w_ptr.contents.values = (c_float * len(scaled_data))(*scaled_data)
        w_ptr.contents.length = len(scaled_data)
        w_ptr.contents.capacity = len(scaled_data)

    def generate(self, audio_path):
        """ Generates a WavePlot from an audio file on the local machine. """

        # Load required data structures
        f_ptr = self.lib.alloc_file()
        i_ptr = self.lib.alloc_info()
        w_ptr = self.lib.alloc_waveplot()
        d_ptr = self.lib.alloc_dr()

        if not os.path.isfile(audio_path):
            raise IOError("File {} not found".format(audio_path))

        self.path = os.path.abspath(audio_path).encode("utf-8")

        result = self.lib.load_file(self.path, f_ptr)
        if result < 0:
            raise IOError("Error loading file {!r}".format(self.path))

        self.lib.get_info(i_ptr, f_ptr)

        self.lib.init_dr(d_ptr, i_ptr)

        a_ptr = self.lib.alloc_audio_samples()
        if not a_ptr:
            raise MemoryError("Ran out of memory attempting to allocate audio"
                              "samples")

        decoded = self.lib.get_samples(a_ptr, f_ptr, i_ptr)
        while decoded >= 0:
            if decoded > 0:
                self.lib.update_waveplot(w_ptr, a_ptr, i_ptr)
                self.lib.update_dr(d_ptr, a_ptr, i_ptr)
            decoded = self.lib.get_samples(a_ptr, f_ptr, i_ptr)

        self.lib.finish_waveplot(w_ptr)
        self.lib.finish_dr(d_ptr, i_ptr)

        # Set instance variables
        waveplot = w_ptr.contents
        dr_data = d_ptr.contents
        info = i_ptr.contents

        self.uuid = None
        self.length = info.duration_secs
        self.trimmed_length = None

        self.dr_level = dr_data.rating

        self.source_type = info.file_format
        self.sample_rate = info.sample_rate
        self.bit_depth = info.bit_depth
        self.bit_rate = info.bit_rate

        self.num_channels = info.num_channels

        self.image_sha1 = None
        self.thumbnail = None
        self.sonic_hash = None

        self.version = self.lib.version()

        self.data = bytes(bytearray(int(200.0*waveplot.values[x])
                                    for x in range(waveplot.length)))

        self.lib.free_dr(d_ptr)
        self.lib.free_waveplot(w_ptr)
        self.lib.free_audio_samples(a_ptr)
        self.lib.free_info(i_ptr)
        self.lib.free_file(f_ptr)

    def generate_preview(self):
        w_ptr = self._get_waveplot_ptr()

        self.lib.resample_waveplot(w_ptr, PREVIEW_IMAGE_WIDTH,
                                   int(PREVIEW_IMAGE_HEIGHT / 2))

        resampled_data = [int(w_ptr.contents.resample[x])
                          for x in range(PREVIEW_IMAGE_WIDTH)]

        w_ptr.contents.values = POINTER(c_float)()

        self.lib.free_waveplot(w_ptr)

        return resampled_data

    def generate_thumbnail(self):
        w_ptr = self._get_waveplot_ptr()

        self.lib.resample_waveplot(w_ptr, THUMB_IMAGE_WIDTH,
                                   int(THUMB_IMAGE_HEIGHT / 2))

        resampled_data = [int(w_ptr.contents.resample[x])
                          for x in range(THUMB_IMAGE_WIDTH)]

        w_ptr.contents.values = POINTER(c_float)()

        self.lib.free_waveplot(w_ptr)

        return resampled_data

    def generate_sonic_hash(self):
        w_ptr = self._get_waveplot_ptr()

        self.lib.resample_waveplot(w_ptr, 16, 1)

        resampled_data = [int(w_ptr.contents.resample[x]) for x in range(16)]

        w_ptr.contents.values = POINTER(c_float)()

        self.lib.free_waveplot(w_ptr)

        # Compute value, converting to ASCII '0' and '1' for int conversion.
        sonic_hash_str = b"".join(chr(ord(x) + 0x30) for x in resampled_data)

        self.sonic_hash = int(sonic_hash_str, 2)

    def get(self, wp_uuid):
        url = SERVER + b'/api/waveplot/{}'.format(wp_uuid)

        response = requests.get(url)

        metadata = response.json()

        response = requests.get(url + "/full")
        waveplot_data = response.json()

        self.uuid = metadata['uuid']
        self.length = metadata['length']
        self.trimmed_length = metadata['trimmed_length']

        self.dr_level = metadata['dr_level']

        self.source_type = metadata['source_type']
        self.sample_rate = metadata['sample_rate']
        self.bit_depth = metadata['bit_depth']
        self.bit_rate = metadata['bit_rate']

        self.num_channels = metadata['num_channels']

        self.image_sha1 = metadata['image_sha1']
        self.thumbnail = metadata['thumbnail']
        self.sonic_hash = metadata['sonic_hash']

        self.version = metadata['version']

        self.data = base64.b64decode(waveplot_data['data'])

    def upload(self, editor_key):
        url = SERVER + b'/api/waveplot'

        data = {
            'editor': editor_key,
            'image': base64.b64encode(zlib.compress(self.data)),
            'dr_level': self.dr_level,
            'length': self.length,
            'trimmed_length': self.length,
            'source_type': self.source_type,
            'sample_rate': self.sample_rate,
            'bit_depth': self.bit_depth,
            'bit_rate': self.bit_rate,
            'num_channels': self.num_channels,
            'version': self.version
        }

        response = requests.post(url, data=json.dumps(data), headers={
            'content-type': 'application/json',
        })

        try:
            data = response.json()
        except simplejson.scanner.JSONDecodeError:
            print("Error: No JSON object in response!")

        if response.status_code < 300:
            self.uuid = data[u'uuid']
            self.image_sha1 = data[u'image_sha1']
            self.thumbnail = data[u'thumbnail']
            self.sonic_hash = data[u'sonic_hash']
        elif response.status_code == 303:
            self.uuid = data['message']
        else:
            print("Error: " + data.get('message', 'Unknown'))

    def link(self, metadata):
        url = SERVER + b'/api/waveplot_context'

        data = metadata
        data.update({'waveplot_uuid': self.uuid})

        response = requests.post(url, data=json.dumps(data), headers={
            'content-type': 'application/json',
        })

        try:
            data = response.json()
        except simplejson.scanner.JSONDecodeError:
            print("Error: No JSON object in response!")

        if response.status_code >= 300:
            print("Error: " + data.get('message', 'Unknown'))

    def match(self):
        raise NotImplementedError
