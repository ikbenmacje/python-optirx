# -*- coding: utf-8 -*-
"""A pure Python library to receive motion capture data from OptiTrack.
"""

from __future__ import print_function


import socket
import struct
from collections import namedtuple
from platform import python_version_tuple


if python_version_tuple()[0] < "3":
    pass
else:
    xrange = range


__version__ = "0.2"
__all__ = [
    # constants:
    'MAX_PACKETSIZE',
    # packet types:
    'SenderData', 'FrameOfData', 'ModelDefs',
    # payload types:
    'RigidBody', 'Skeleton', 'LabeledMarker', 'ModelDataset',
    # functions:
    'mkcmdsock', 'mkdatasock', 'unpack']


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


DATASET_MARKERSET =           0  # PacketClient.cpp:778
DATASET_RIGIDBODY =           1  # PacketClient.cpp:800
DATASET_SKELETON =            2  # PacketClient.cpp:827


MAX_NAMELENGTH =              256
MAX_PAYLOADSIZE =             100000
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
#  - union of possible payloads (MAX_PAYLOADSIZE bytes)
PACKET_HEADER_FORMAT = "=2H"
PACKET_FORMAT = PACKET_HEADER_FORMAT + ("%dB" % MAX_PAYLOADSIZE)
MAX_PACKETSIZE = struct.calcsize(PACKET_FORMAT)


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


# Skeleton (NetNet >= 2.1) is a collection of rigid bodies:
Skeleton = namedtuple("Skeleton", "id rigid_bodies")


# LabeledMarker (NatNet >= 2.3)
LabeledMarker = namedtuple("LabeledMarker", "id position size")


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
FrameOfData = namedtuple("FrameOfData", "frameno sets other_markers rigid_bodies skeletons labeled_markers latency timecode")


# type can be one of DATASET_MARKERSET, DATASET_RIGIDBODY, DATASET_SKELETON
# name is a string (possibly empty)
# data can be
#   - a list of strings (names of the markers for a markerset)
#   - a list of rigid bodies' dictionaries
ModelDataset = namedtuple("ModelDataset", "type name data")


# defs is a list of ModelDataset elements
ModelDefs = namedtuple("ModelDefs", "datasets")


def _version_is_at_least(version, major, minor=None):
    vmajor, vminor = version[:2]
    return (vmajor > major) or ((vmajor == major) and ((not minor) or (vminor >= minor)))


def _unpack_head(head_fmt, data):
    """Unpack some bytes at the head of the data.
    Return unpacked values and the rest of the data.

    >>> _unpack_head('>h', b'\2\1_therest')
    ((513,), '_therest')

    """
    sz = struct.calcsize(head_fmt)
    vals = struct.unpack(head_fmt, data[:sz])
    return vals, data[sz:]


def _unpack_cstring(data, maxstrlen):
    """"Read a null-terminated string from the head of the data.
    Return the string and the rest of the data.

    >>> _unpack_cstring("abc%cfoobar" % 0, 6)
    ('abc', 'foobar')

    """
    databuf = data[:maxstrlen]
    databuflen = min(len(databuf), maxstrlen)
    (strbuf,) = struct.unpack("%ds" % databuflen, databuf)
    s = strbuf.split(b"\0", 1)[0]
    sz = len(s) + 1
    return s, data[sz:]


def _unpack_sender(payload, size):
    """Read Sender structure from the head of the data.
    Return SenderData and the rest of the data."""
    (appname, v1,v2,v3,v4, nv1,nv2,nv3,nv4), data = _unpack_head(SENDER_FORMAT, payload)
    appname = appname.split(b"\0",1)[0] if appname else ""
    version = (v1,v2,v3,v4)
    natnet_version = (nv1,nv2,nv3,nv4)
    return SenderData(appname, version, natnet_version), data


def _unpack_markers(data, version):
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
        markers, data = _unpack_markers(data, version)
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


def _unpack_skeletons(data, version):
    # not tested
    if not _version_is_at_least(version, 2, 1):  # PacketClient.cpp:653
        return [], data
    (nskels,), data = _unpack_head("i", data)
    skels = []
    for i in xrange(nskels):
        (skelid,), data = _unpack_head("i", data)
        rbodies, data = _unpack_rigid_bodies(data, version)
        skels.append(Skeleton(id=id, rigid_bodies=rbodies))
    return skels, data


def _unpack_labeled_markers(data, version):
    if not _version_is_at_least(version, 2, 3):
        return [], data
    (nmarkers,), data = _unpack_head("i", data)
    lmarkers = []
    for i in xrange(nmarkers):
        (id,x,y,z,size), data = _unpack_head("i4f", data)
        lmarkers.append(LabeledMarker(id, (x, y, z), size))
    return lmarkers, data


def _unpack_frameofdata(data, version):
    (frameno, nsets), data = _unpack_head("ii", data)
    # identified marker sets
    sets = {}
    for i in xrange(nsets):
        setname, data = _unpack_cstring(data, MAX_NAMELENGTH)
        markers, data = _unpack_markers(data, version)
        sets[setname] = markers
    # other (unidentified) markers
    markers, data = _unpack_markers(data, version)
    bodies, data = _unpack_rigid_bodies(data, version)
    skels, data = _unpack_skeletons(data, version)
    lmarkers, data = _unpack_labeled_markers(data, version)
    (latency,timecode1,timecode2,eod), data = _unpack_head("fIIi", data)
    assert eod == 0, "End-of-data marker is not 0."
    fod = FrameOfData(frameno=frameno,
                      sets=sets,
                      other_markers=markers,
                      rigid_bodies=bodies,
                      skeletons=skels,
                      labeled_markers=lmarkers,
                      latency=latency,
                      timecode=(timecode1, timecode2))
    return fod, data


def _unpack_modeldef(data, version):
    """Return ModelDefs and the rest of the data.
    """
    # PacketClient.cpp:765
    (ndatasets,), data = _unpack_head("i", data)
    datasets = []
    for i in xrange(ndatasets):
        (dtype,), data = _unpack_head("i", data)
        if dtype == DATASET_MARKERSET:
            name, data = _unpack_cstring(data, MAX_NAMELENGTH)
            (nmarkers,), data = _unpack_head("i", data)
            mrk_names = []
            for j in xrange(nMarkers):
                mrk_name, data = _unpack_cstring(data, MAX_NAMELENGTH)
                mrk_names.append(mrk_name)
            dset = ModelDataset(DATASET_MARKERSET, name, mrk_names)
            datasets.append(dset)
        elif dtype == DATASET_RIGIDBODY:
            if _version_is_at_least(version, 2, 0):
                name, data = _unpack_cstring(data, MAX_NAMELENGTH)
            else:
                name = ""
            (rbid, parent, xoff, yoff, zoff), data = _unpack_head("2i3f", data)
            dset = ModelDataset(DATASET_RIGIDBODY, name,
                            [{"id": rbid,
                              "parent": parent,
                              "offset": (xoff, yoff, zoff)}])
            datasets.append(dset)
        elif dtype == DATASET_SKELETON:
            name, data = _unpack_cstring(data, MAX_NAMELENGTH)
            (skid, nbodies), data = _unpack_head("2i", data)
            bodies = []
            for j in xrange(nbodies):
                if _version_is_at_least(version, 2, 0):
                    bname, data = _unpack_cstring(data, MAX_NAMELENGTH)
                else:
                    bname = ""
                (rbid, parent, xoff, yoff, zoff), data = _unpack_head("2i3f", data)
                body = {"id": rbid,
                        "parent": parent,
                        "offset": (xoff, yoff, zoff)}
                bodies.append(body)
            dset = ModelDataset(DATASET_RIGIDBODY, name, bodies)
            datasets.append(dset)
        else:
            raise NotImplementedError("dataset type " + str(dtype))
    return ModelDefs(datasets), data


def unpack(data, version=(2, 5, 0, 0)):
    """Unpack raw NatNet packet data.

    Arguments:
      data     byte buffer
      version  version of the NatNet protocol (a tuple of integers)
    """
    if not data or len(data) < 4:
        return None
    (msgtype, nbytes), data = _unpack_head(PACKET_HEADER_FORMAT, data)
    if msgtype == NAT_PINGRESPONSE:
        sender, data = _unpack_sender(data, nbytes)
        return sender
    elif msgtype == NAT_FRAMEOFDATA:
        frame, data = _unpack_frameofdata(data, version)
        return frame
    elif msgtype == NAT_MODELDEF:
        modeldef, data = _unpack_modeldef(data, version)
        return modeldef
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
    try:
        from simplejson import dumps, encoder
        encoder.FLOAT_REPR = lambda o: ("%.4f" % o)
    except ImportError:
        from json import dumps, encoder
        encoder.FLOAT_REPR = lambda o: ("%.4f" % o)

    dsock = mkdatasock()
    version = (2, 5, 0, 0)
    while True:
        data = dsock.recv(MAX_PACKETSIZE)
        packet = unpack(data, version=version)
        if type(packet) is SenderData:
            version = packet.natnet_version
        if type(packet) in [SenderData, ModelDefs, FrameOfData]:
            print(dumps(packet, namedtuple_as_object=1, indent=4))


if __name__ == "__main__":
    demo_recv_data()
