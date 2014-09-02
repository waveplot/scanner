from __future__ import print_function

from multiprocessing import Queue, Process
from Queue import Empty as QEmpty
import os
import sys
from waveplot.waveplot import WavePlot
from mutagenx import File
import json

def pprint(data):
     return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))

def scan(scan_queue, upload_queue, num):
    try:
        while 1:
            path = scan_queue.get(timeout=10)
            if os.path.splitext(path)[1] in exts:
                wp = WavePlot()
                wp.generate(path)
                wp.lib = None

                # Get metadata, if possible
                tags = File(path, easy = True)
                if tags:
                    metadata = {
                        'recording_mbid': tags.get(u"musicbrainz_trackid", [None])[0],
                        'release_mbid': tags.get(u"musicbrainz_albumid", [None])[0],
                        'track_number': tags.get(u"tracknumber", [None])[0],
                        'disc_number': tags.get(u"discnumber", [None])[0],
                    }

                upload_queue.put((wp, metadata))
    except QEmpty:
        pass

def upload(queue, key):
    try:
        while 1:
            wp, metadata = queue.get(timeout=10)
            wp.upload(key)
            wp.link(metadata)
    except QEmpty:
        pass

exts = [".mp3",".flac"]

if __name__ == '__main__':

    if len(sys.argv) != 2:
        sys.exit(-1)

    if not os.path.exists(sys.argv[1]):
        sys.exit(-1)

    key = raw_input("Please enter your WavePlot editor key to continue... ")

    directory = unicode(os.path.abspath(sys.argv[1]), encoding=sys.getfilesystemencoding())

    scan_list = Queue()
    upload_list = Queue()

    parallel_processes = 4
    scanners = [Process(target=scan, args=(scan_list, upload_list, p)) for p in range(parallel_processes)]
    uploader = Process(target=upload, args=(upload_list, key))

    for s in scanners:
        s.start()
    uploader.start()

    try:
        total_items = 0
        for directory, directories, filenames in os.walk(directory):
            for filename in filenames:
                scan_list.put(os.path.join(directory,filename))
                total_items += 1

        print("Waiting for scanning processes to complete... (please be patient)")

        queue_size = scan_list.qsize()
        while queue_size > 0:
            scanners[0].join(timeout = 1)
            queue_size = scan_list.qsize()
            if queue_size == 0:
                print("\nFinishing processing, please wait..", end="")
                sys.stdout.flush()
            else:
                print("{:.0%}...".format(1.0 - float(queue_size) / total_items), end="")
                sys.stdout.flush()

        for s in scanners:
            print(".",end="")
            sys.stdout.flush()
            s.join()
        print("")

        print("Done!")
    except KeyboardInterrupt:
        for s in scanners:
            s.terminate()


