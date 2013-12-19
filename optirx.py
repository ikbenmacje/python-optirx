# -*- coding: utf-8 -*-
from __future__ import print_function


import socket
import struct
from collections import namedtuple
try:
    from simplejson import dumps, encoder
    encoder.FLOAT_REPR = lambda o: ("%.4f" % o)
except ImportError:
    from json import dumps, encoder
    encoder.FLOAT_REPR = lambda o: ("%.4f" % o)


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


# rigid body payload (PacketClient.cpp:586)
#  - id (int, 32 bits)
#  - x,y,z (3 floats, 3x32 bits)
#  - qx,qy,qz,qw (4 floats, 4x32 bits)
RIGIDBODY_FORMAT =  "=i3f4f"
# RigidBody:
#   id is an integer
#   position is a triple of coordinates
#   orientation is a quaternion (qx, qy, qz, qw)
#   markers is a list of triples
#   mrk_ids is a list of integers or None (NatNet version < 2.0)
#   mrk_sizes is a list of floats or None (NatNet version < 2.0)
#   mrk_mean_error is a float or None (NatNet version < 2.0)
RigidBody = namedtuple("RigidBody",
                       "id position orientation markers mrk_ids mrk_sizes mrk_mean_error")


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
FrameOfData = namedtuple("FrameOfData", "frameno sets other_markers rigid_bodies")


def _version_is_at_least(version, major, minor=None):
    vmajor, vminor = version[:2]
    return (vmajor > major) or ((vmajor == major) and ((not minor) or (vminor >= minor)))


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
    databuf = data[:maxstrlen]
    databuflen = min(len(databuf), maxstrlen)
    (strbuf,) = struct.unpack("%ds" % databuflen, databuf)
    s = strbuf.split("\0", 1)[0]
    sz = len(s) + 1
    return s, data[sz:]


def _unpack_sender(payload, size):
    """Read Sender structure from the head of the data.
    Return SenderData and the rest of the data."""
    (appname, v1,v2,v3,v4, nv1,nv2,nv3,nv4), data = _unpack_head(SENDER_FORMAT, payload)
    appname = appname.split("\0",1)[0] if appname else ""
    version = (v1,v2,v3,v4)
    natnet_version = (nv1,nv2,nv3,nv4)
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


def _unpack_rigid_bodies(data, version):
    """Read a sequence of rigid bodies from the head of the data.
    Return a list of RigidBody tuples and the rest of the data."""
    (nbodies,), data = _unpack_head("i", data)
    rbodies = []
    for i in xrange(nbodies):
        (rbid, x, y, z, qx, qy, qz, qw), data = _unpack_head(RIGIDBODY_FORMAT, data)
        markers, data = _unpack_markers(data)
        if _version_is_at_least(version, 2, 0):  # PacketClient.cpp:607
            nmarkers = len(markers)
            mrk_ids, data = _unpack_head(str(nmarkers) + "i", data)
            mrk_sizes, data = _unpack_head(str(nmarkers) + "f", data)
            (mrk_mean_error,), data = _unpack_head("f", data)
        else:
            mrk_ids, mrk_sizes, mrk_mean_error = None, None, None
        rb = RigidBody(id=rbid,
                       position=(x,y,z),
                       orientation=(qx,qy,qz,qw),
                       markers=markers,
                       mrk_ids=mrk_ids,
                       mrk_sizes=mrk_sizes,
                       mrk_mean_error=mrk_mean_error)
        rbodies.append(rb)
    return rbodies, data


def _unpack_frameofdata(data, version):
    (frameno, nsets), data = _unpack_head("ii", data)
    # identified marker sets
    sets = {}
    for i in xrange(nsets):
        setname, data = _unpack_cstring(data, MAX_NAMELENGTH)
        markers, data = _unpack_markers(data)
        sets[setname] = markers
    # other (unidentified) markers
    markers, data = _unpack_markers(data)
    bodies, data = _unpack_rigid_bodies(data, version)
    # TODO: implement rigid bodies, skeletons, etc.
    fod = FrameOfData(frameno=frameno,
                      sets=sets,
                      other_markers=markers,
                      rigid_bodies=bodies)
    return fod, data


def unpack(data, version=(2, 5, 0, 0)):
    """Unpack raw NatNet packet data.

    Arguments:
      data     byte buffer
      version  version of the NatNet protocol (a tuple of integers)
    """
    if not data or len(data) < 4:
        return None
    fmt = PACKET_FORMAT
    (msgtype, nbytes), data = _unpack_head(fmt[:4], data)
    if msgtype == NAT_PINGRESPONSE:
        sender, data = _unpack_sender(data, nbytes)
        return sender
    elif msgtype == NAT_FRAMEOFDATA:
        frame, data = _unpack_frameofdata(data, version)
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


def demo_recv_data():
    dsock = mkdatasock()
    bufsize = struct.calcsize(PACKET_FORMAT)
    version = (2, 5, 0, 0)
    while True:
        data = dsock.recv(bufsize)
        packet = unpack(data, version=version)
        if type(packet) is SenderData:
            version = SenderData.natnet_version
        if type(packet) in [SenderData, FrameOfData]:
            print(dumps(packet.__dict__, namedtuple_as_object=1, indent=4))


if __name__ == "__main__":
    demo_recv_data()
