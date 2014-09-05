#!/usr/bin/env python2.7
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

"""This module is designed to be run from the command line to scan a directory
of files and generate WavePlots for all of them. It then attempts to upload
the WavePlots to a central server (http://waveplot.net).
"""

from __future__ import print_function

import os
import sys
import json
import mutagen
import argparse

from multiprocessing import Process, Queue

from Queue import Empty as QEmpty

from waveplot import WavePlot


NUM_SCAN_PROCESSES = 4


def pprint(data):
    return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))


def is_recognised_filetype(path):
    """Checks whether the provided path has a recognised extension."""

    recognised_exts = [".mp3", ".flac"]
    if os.path.splitext(path)[1] in recognised_exts:
        return True
    else:
        return False


def get_metadata(path):
    tags = mutagen.File(path, easy=True)

    if tags is not None:
        metadata = {
            'recording_mbid': tags.get(u"musicbrainz_trackid", [None])[0],
            'release_mbid': tags.get(u"musicbrainz_albumid", [None])[0],
            'track_number': tags.get(u"tracknumber", [None])[0],
            'disc_number': tags.get(u"discnumber", [None])[0],
        }

        return metadata

    return None


def scan(scan_queue, upload_queue):
    try:
        while 1:
            path = scan_queue.get(timeout=10)

            waveplot = WavePlot()
            waveplot.generate(path)
            waveplot.lib = None

            # Get metadata, if possible
            metadata = get_metadata(path)

            upload_queue.put((waveplot, metadata))
    except QEmpty:
        pass


def find_files(path, scan_queue):
    num_found_files = 0
    filesystem_encoding = sys.getfilesystemencoding()

    for directory, directories, filenames in os.walk(path):
        for filename in filenames:
            if is_recognised_filetype(filename):
                path = os.path.join(directory, filename)
                path = path.decode(filesystem_encoding)
                scan_queue.put(path)
                num_found_files += 1

    return num_found_files


def main():
    parser = argparse.ArgumentParser(
        description='Generates WavePlots from a directory of music files.'
    )

    parser.add_argument(
        'key',
        type=int,
        help='your WavePlot editor key, required to upload data to the server'
    )

    parser.add_argument(
        'path',
        help='the path to the music directory to be scanned'
    )

    args = parser.parse_args()

    scan_queue = Queue()
    upload_queue = Queue()

    scanners = [
        Process(target=scan, args=(scan_queue, upload_queue))
        for i in range(NUM_SCAN_PROCESSES)
    ]

    for scanner in scanners:
        scanner.start()

    try:
        num_found_files = find_files(args.path, scan_queue)

        print("Directory scanned, please wait while WavePlots are uploaded...")

        num_uploaded_files = 0
        try:
            while 1:
                waveplot, metadata = upload_queue.get(timeout=10)
                waveplot.upload(args.key)
                waveplot.link(metadata)
                num_uploaded_files += 1
                print("{}/{}: {} ({})".format(num_uploaded_files,
                                              num_found_files, waveplot.uuid,
                                              os.path.relpath(waveplot.path,
                                                              args.path)))
        except QEmpty:
            pass

        for scanner in scanners:
            scanner.join()

    except KeyboardInterrupt:
        for scanner in scanners:
            scanner.terminate()
        print('')

if __name__ == '__main__':
    main()
