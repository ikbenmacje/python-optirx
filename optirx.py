# -*- coding: utf-8 -*-
from __future__ import print_function


import socket
import struct
from collections import namedtuple


###
### Some constants as defined in NatNet SDK example ###
###

# NATNET message ids (actually codes, they are not unique)
NAT_PING =                    0
NAT_PINGRESPONSE =            1
NAT_REQUEST =                 2
NAT_RESPONSE =                3
NAT_REQUEST_MODELDEF =        4
NAT_MODELDEF =                5
NAT_REQUEST_FRAMEOFDATA =     6
NAT_FRAMEOFDATA =             7
NAT_MESSAGESTRING =           8
NAT_UNRECOGNIZED_REQUEST =    100
UNDEFINED =                   999999.9999
NAT_TYPES = { NAT_PING: "ping",
              NAT_PINGRESPONSE: "pong",
              NAT_REQUEST: "request",
              NAT_RESPONSE: "response",
              NAT_REQUEST_MODELDEF: "request_modeldef",
              NAT_MODELDEF: "modeldef",
              NAT_REQUEST_FRAMEOFDATA: "request_frameofdata",
              NAT_FRAMEOFDATA: "frameofdata",
              NAT_MESSAGESTRING: "messagestring",
              NAT_UNRECOGNIZED_REQUEST: "unrecognized" }


MAX_NAMELENGTH =              256
MAX_PACKETSIZE =              100000              # max size of packet (actual size is dynamic)
MULTICAST_ADDRESS =           "239.255.42.99"     # IANA, local network
PORT_COMMAND =                1510
PORT_DATA =                   1511                # Default multicast group
SOCKET_BUFSIZE = 0x100000

###
### NatNet packet format ###
###

# sPacket struct (PacketClient.cpp:65)
#  - iMessage (unsigned short),
#  - nDataBytes (unsigned short),
#  - union of possible payloads (MAX_PACKETSIZE bytes)
PACKET_FORMAT =  "=" + "2H" + ("%dB" % MAX_PACKETSIZE)

# sender payload struct (PacketClient.cpp:57)
#  - szName (string MAX_NAMELENGTH),
#  - Version (4 unsigned chars),
#  - NatNetVersion (4 unsigned chars)
SENDER_FORMAT =  "=" + ("%ds" % MAX_NAMELENGTH) + "4B4B"
SenderData = namedtuple("SenderData", "appname version natnet_version")


# frame payload format (PacketClient.cpp:537) cannot be unpacked by
# struct.unpack, because contains variable-length elements
#  - frameNumber (int),
#  - number of data sets nMarkerSets (int),
#  - MARKERSETS, each of them:
#     * null-terminated set name (max MAX_NAMELENGTH bytes),
#     * marker count nMarkers (int),
#     * MARKERS, each of them:
#        + x (float),
#        + y (float),
#        + z (float),
#  - UNIDENTIFIED_MARKERS:
#     * nOtherMarkers (int),
#     * MARKERS, each of them:
#        + x (float),
#        + y (float),
#        + z (float),
#  - RIGID_BODIES (...)
#  - SKELETONS (...), ver >= 2.1
#  - LABELED_MARKERS (...), ver >= 2.3
#  - latency (float),
#  - timecode (int, int),
#  - end of data tag (int).
FrameOfData = namedtuple("FrameOfData", "frameno sets other_markers")


def _unpack_head(head_fmt, data):
    """Unpack some bytes at the head of the data.
    Return unpacked values and the rest of the data.

    >>> _unpack_head('>h', '\2\0_therest')
    ((512,), '_therest')

    """
    sz = struct.calcsize(head_fmt)
    vals = struct.unpack(head_fmt, data[:sz])
    return vals, data[sz:]


def _unpack_cstring(data, maxstrlen):
    """"Read a null-terminated string from the head of the data.
    Return the string and the rest of the data.

    >>> _unpack_cstring("abc\0foobar", 6)
    ('abc', 'foobar')

    """
    (strbuf,) = struct.unpack("%ds" % maxstrlen, data[:maxstrlen])
    s = strbuf.split("\0", 1)[0]
    sz = len(s) + 1
    return s, data[sz:]


def _unpack_sender(payload, size):
    (appname, v1,v2,v3,v4, nv1,nv2,nv3,nv4), data = _unpack_head(SENDER_FORMAT, payload)
    appname = appname.split("\0",1)[0] if appname else ""
    version = "%d.%d.%d.%d" %(v1,v2,v3,v4)
    natnet_version = "%d.%d.%d.%d" % (nv1,nv2,nv3,nv4)
    return SenderData(appname, version, natnet_version), data


def _unpack_markers(data):
    """Read a sequence of markers from the head of the data.
    Return a list of coordinate triples and the rest of the data."""
    (nmarkers,), data = _unpack_head("i", data)
    markers = []
    for i in xrange(nmarkers):
        (x, y, z), data = _unpack_head("3f", data)
        markers.append((x,y,z))
    return markers, data


def _unpack_frameofdata(data):
    (frameno, nsets), data = _unpack_head("ii", data)
    # identified marker sets
    sets = {}
    for i in xrange(nsets):
        setname, data = _unpack_cstring(data, MAX_NAMELENGTH)
        markers, data = _unpack_markers(data)
        sets[setname] = markers
    # other (unidentified) markers
    markers, data = _unpack_markers(data)
    # TODO: implement rigid bodies, skeletons, etc.
    return FrameOfData(frameno=frameno, sets=sets, other_markers=markers), data


def unpack(data):
    "Unpack raw NatNet packet data."
    if not data or len(data) < 4:
        return None
    fmt = PACKET_FORMAT
    (msgtype, nbytes), data = _unpack_head(fmt[:4], data)
    if msgtype == NAT_PINGRESPONSE:
        sender, data = _unpack_sender(data, nbytes)
        return sender
    elif msgtype == NAT_FRAMEOFDATA:
        frame, data = _unpack_frameofdata(data)
        return frame
    else:
        # TODO: implement other message types
        raise NotImplementedError("packet type " + str(NAT_TYPES.get(msgtype, msgtype)))


###
### Communication sockets ###
###


# TODO: implement control thread
# TODO: implement data thread


def gethostip():
    return socket.gethostbyname(socket.gethostname())


def mkcmdsock(ip_address=None, port=0):
    "Create a command socket."
    ip_address = gethostip() if not ip_address else ip_address
    cmdsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    cmdsock.bind((ip_address, port))
    cmdsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    cmdsock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFSIZE)
    return cmdsock


def mkdatasock(ip_address=None, multicast_address=MULTICAST_ADDRESS, port=PORT_DATA):
    "Create a data socket."
    ip_address = gethostip() if not ip_address else ip_address
    datasock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    datasock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    datasock.bind((ip_address, port))
    # join a multicast group
    mreq = struct.pack("=4sl", socket.inet_aton(multicast_address), socket.INADDR_ANY)
    datasock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    datasock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFSIZE)
    return datasock


###
### Demo mode: connect to Optitrack on the same machine, print recieved data.
###


def _demo_print_markers(markers, depth):
    for x, y, z in markers:
        print("  "*depth + "- [ % 7.1f,  % 7.1f,  % 7.1f ]" % (x*1000, y*1000, z*1000))


def _demo_print_frame(frame):

    if not (frame.other_markers or frame.sets):
        return  # don't print empty frames

    print("- frame_of_data:")
    print("    frameno: %d" % frame.frameno)

    if frame.sets:
        print("    sets:")
        for s in frame.sets:
            print("      - setname:", s)
            print("        markers:")
            _demo_print_markers(frame.sets[s], depth=5)

    if frame.other_markers:
        print("    other_markers:")
        _demo_print_markers(frame.other_markers, depth=3)

    print()


def _demo_print_sender(sender):
    print("- sender:")
    print("    appname:", sender.appname)
    print("    version:", sender.version)
    print("    natnet_version:", sender.natnet_version)
    print()


def demo_recv_data():
    dsock = mkdatasock()
    bufsize = struct.calcsize(PACKET_FORMAT)
    while True:
        data = dsock.recv(bufsize)
        packet = unpack(data)
        if type(packet) is SenderData:
            _demo_print_sender(packet)
        elif type(packet) is FrameOfData:
            _demo_print_frame(packet)
        else:
            print(packet)


if __name__ == "__main__":
    demo_recv_data()
