OptiRX
======

A pure Python library to receive motion capture data from OptiTrack
Streaming Engine.

OptiTrack is a line of motion capture products by NaturalPoint. Their
software can broadcast motion capture data via a documented binary
protocol. It is supposed to be used together with the proprietary
NatNet SDK, which, unfortunately, is not available for Python, nor
cannot be used with free toolchains (GCC, Clang). OptiRX is based on
the direct depacketization example from the SDK and does not use
NatNet SDK.

Install
-------

::

    pip install optirx


Compatibility
-------------

Tracking Tools 2.5.0; Motive 1.5.x (NatNet 2.5.0.0), 1.7.x (NatNet 2.7.0.0).


Build Status
------------

.. image:: https://drone.io/bitbucket.org/astanin/python-optirx/status.png
   :alt: build status
   :target: https://drone.io/bitbucket.org/astanin/python-optirx/latest


Usage
-----

Assuming that Tracking Tools or Motion runs on the same machine and
broadcasting is enabled with the default parameters, this code
receives and prints all data frames::

    import optirx as rx

    dsock = rx.mkdatasock()
    version = (2, 7, 0, 0)  # NatNet version to use
    while True:
        data = dsock.recv(rx.MAX_PACKETSIZE)
        packet = rx.unpack(data, version=version)
        if type(packet) is rx.SenderData:
            version = packet.natnet_version
        print packet


Alternatives
------------

- use VRPN streaming protocol.
- use Matlab or Microsoft toolchains.
- use PyNatNet and NatNet SDK


License
-------

MIT
