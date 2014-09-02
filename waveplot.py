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

import os
import requests
import uuid
import base64
import json
import zlib

from ctypes import Structure, c_char_p, c_uint32, c_uint8, c_uint16, POINTER, \
    c_float, c_size_t, cdll

THUMB_IMAGE_WIDTH = 50
THUMB_IMAGE_HEIGHT = 21

PREVIEW_IMAGE_WIDTH = 400
PREVIEW_IMAGE_HEIGHT = 151


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
    def __init__(self, *args, **kwargs):
        super(WavePlot, self).__init__(*args, **kwargs)

        self.lib = None

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
        self.thumbnail_c = None
        self.sonic_hash = None

        self.version = None

        self.data = None

    def _init_libwaveplot(self):
        """ Initializes the libwaveplot library, which should have been
        installed on this machine along with python-waveplot. If not, raise an
        Exception to show that the library wasn't found and the installation is
        bad. """

        self.lib = cdll.LoadLibrary("libwaveplot.so.1.0")

        self.lib.init()
        self.lib.alloc_file.restype = POINTER(_File)
        self.lib.alloc_info.restype = POINTER(_Info)
        self.lib.alloc_audio_samples.restype = POINTER(_AudioSamples)
        self.lib.alloc_waveplot.restype = POINTER(_WavePlot)
        self.lib.alloc_dr.restype = POINTER(_DR)
        self.lib.version.restype = c_char_p

    @staticmethod
    def resample_data(data, target_length, target_amplitude):
        # Calculate the number of data values per new data value
        print(len(data))
        resample_factor = float(len(data)) / target_length

        # Check whether it's a down-sample
        if resample_factor > 1.0:
            new_data = []
            current_weighting = resample_factor
            current_value = 0.0

            for value in data:
                value = ord(value)

                current_value += value * min(current_weighting, 1.0)
                current_weighting -= 1.0

                # Negative, cap off previous value, make new
                if current_weighting <= 0.0:
                    new_data.append(current_value / resample_factor)
                    current_value = -value * current_weighting
                    current_weighting += resample_factor
        else:
            new_data = [ord(value) for value in data]

        amplitude_factor = float(target_amplitude) / 200

        return "".join(chr(int((v*amplitude_factor) + 0.5)) for v in new_data)

    def make_hash(self):
        # Restrict data to 5% points (trimmed length)
        start_index = end_index = 0
        for i in range(0,len(self.data)):
            if ord(self.data[i]) > 10:
                start_index = i
                break

        for i in range(len(self.data) - 1,-1,-1):
            if ord(self.data[i]) > 10:
                end_index = i
                break

        #print(start_index)
        #print(end_index)

        image_data = self.data[start_index:end_index+1]

        # Compute value, converting to ASCII '0' and '1' for int conversion.
        barcode_str = b"".join(chr(ord(x) + 0x30) for x in
                              WavePlot.resample_data(image_data, 16, 1))

        self.barcode = int(barcode_str,2)

    def generate(self, audio_path):
        """ Generates a WavePlot from an audio file on the local machine. """

        self.path = audio_path

        if self.lib is None:
            self._init_libwaveplot()

        # Load required data structures
        f_ptr = self.lib.alloc_file()
        i_ptr = self.lib.alloc_info()
        w_ptr = self.lib.alloc_waveplot()
        d_ptr = self.lib.alloc_dr()

        audio_path = audio_path.encode("utf-8")
        os.path.abspath(audio_path)

        if not os.path.isfile(audio_path):
            return

        self.lib.load_file(audio_path, f_ptr)
        self.lib.get_info(i_ptr, f_ptr)

        self.lib.init_dr(d_ptr, i_ptr)

        a_ptr = self.lib.alloc_audio_samples()

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
        if self.lib is None:
            self._init_libwaveplot()

        w_ptr = self.lib.alloc_waveplot()

        normalized_data = [float(x)/200.0 for x in bytearray(self.data)]

        w_ptr.contents.values = (c_float * len(normalized_data))(*normalized_data)
        w_ptr.contents.length = len(normalized_data)
        w_ptr.contents.capacity = len(normalized_data)

        self.lib.resample_waveplot(w_ptr, PREVIEW_IMAGE_WIDTH, int(PREVIEW_IMAGE_HEIGHT / 2));

        resampled_data = [int(w_ptr.contents.resample[x]) for x in range(PREVIEW_IMAGE_WIDTH)]

        w_ptr.contents.values = POINTER(c_float)()

        self.lib.free_waveplot(w_ptr)

        return resampled_data

    def generate_thumbnail(self):
        if self.lib is None:
            self._init_libwaveplot()

        w_ptr = self.lib.alloc_waveplot()

        normalized_data = [float(x)/200.0 for x in bytearray(self.data)]

        w_ptr.contents.values = (c_float * len(normalized_data))(*normalized_data)
        w_ptr.contents.length = len(normalized_data)
        w_ptr.contents.capacity = len(normalized_data)

        self.lib.resample_waveplot(w_ptr, THUMB_IMAGE_WIDTH, int(THUMB_IMAGE_HEIGHT / 2));

        resampled_data = [int(w_ptr.contents.resample[x]) for x in range(THUMB_IMAGE_WIDTH)]

        w_ptr.contents.values = POINTER(c_float)()

        self.lib.free_waveplot(w_ptr)

        return resampled_data

    def get(self, uuid):
        url = b"http://waveplot.net/api/waveplot/{}"

        response = requests.get(url.format(uuid))

        data = response.json()

        self.uuid = uuid
        self.length = data['length']
        self.trimmed_length = data['trimmed_length']

        self.dr_level = data['dr_level']

        self.source_type = data['source_type']
        self.sample_rate = data['sample_rate']
        self.bit_depth = data['bit_depth']
        self.bit_rate = data['bit_rate']

        self.num_channels = data['num_channels']

        self.image_sha1 = data['image_sha1']
        self.thumbnail = data['thumbnail']
        self.sonic_hash = data['sonic_hash']

        self.version = data['version']

        response = requests.get(url.format(uuid)+"/full")
        data = response.json()
        self.data = base64.b64decode(data['data'])

    def upload(self, editor_key):
        url = b'http://waveplot.net/api/waveplot'

        data = {
            'editor':editor_key,
            'image': base64.b64encode(zlib.compress(self.data)),
            'dr_level':self.dr_level,
            'length':self.length,
            'trimmed_length':self.length,
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

        print(response.content)
        data = response.json()
        if response.status_code == 303:
            self.uuid = data['message']
        else:
            print(data)
            self.uuid = data[u'uuid']
            self.image_sha1 = data[u'image_sha1']
            self.thumbnail = data[u'thumbnail']
            self.sonic_hash = data[u'sonic_hash']

    def link(self, metadata):
        url = b'http://waveplot.net/api/waveplot_context'

        data = metadata
        data.update({'waveplot_uuid':self.uuid})
        print data

        response = requests.post(url, data=json.dumps(data), headers={
            'content-type': 'application/json',
        })

    def match(self):
        pass
        #self.make_hash()


        #self.preview_data = WavePlot.resample_data(self.data, PREVIEW_IMAGE_WIDTH,
                                          #int(PREVIEW_IMAGE_HEIGHT / 2))

        #print(self.barcode)
        #print([self.thumbnail_c[x] for x in range(THUMB_IMAGE_WIDTH)])
