"""Capture and dump N binary Motive packets.

Usage:

    python dump_packets.py <motive.version> <number-of-packets>

"""

from __future__ import print_function
import optirx as rx
import sys
import os


def main():
    version, max_count = sys.argv[1:]
    max_count = int(max_count)
    dsock = rx.mkdatasock()
    count = 0
    while count < max_count:
        data = dsock.recv(rx.MAX_PACKETSIZE)
        fname = os.path.join("test", "data", "frame-motive-%s-%03d.bin" % (version, count))
        with open(fname, "wb") as dumpfile:
            dumpfile.write(bytes(data))
            print("dumped", fname)
        count += 1


if __name__ == "__main__":
    main()