"""OptiRX demo: connect to Optitrack on the same machine, print received data.

Usage:

    python optrix_demo.py [number_of_packets_to_print] [natnet_version]

where natnet_version is 2500, 2600, 2700 etc
for Motive 1.5, 1.6 betas, and 1.7.x respectively.
"""


from __future__ import print_function
import optirx as rx
import sys


def demo_recv_data():
    # pretty-printer for parsed
    try:
        from simplejson import dumps, encoder
        encoder.FLOAT_REPR = lambda o: ("%.4f" % o)
    except ImportError:
        from json import dumps, encoder
        encoder.FLOAT_REPR = lambda o: ("%.4f" % o)

    # the first optional command line argument:
    # if given, the number of packets to dump
    if sys.argv[1:]:
        max_count = int(sys.argv[1])
    else:
        max_count = float("inf")

    # the second optional command line argument
    # is the version string of the NatNet server;
    # may be necessary to receive data without
    # the initial SenderData packet
    if sys.argv[2:]:
        version = tuple(map(int, sys.argv[2]))
    else:
        version = (2, 7, 0, 0)  # the latest SDK version

    dsock = rx.mkdatasock()
    count = 0
    while count < max_count:
        data = dsock.recv(rx.MAX_PACKETSIZE)
        packet = rx.unpack(data, version=version)
        if type(packet) is rx.SenderData:
            version = packet.natnet_version
            print("NatNet version received:", version)
        if type(packet) in [rx.SenderData, rx.ModelDefs, rx.FrameOfData]:
            print(dumps(packet._asdict(), indent=4))
        count += 1


if __name__ == "__main__":
    demo_recv_data()
