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

Compatibility: Tracking Tools 2.5.0.

Alternatives:

- use VRPN streaming protocol.
- use Matlab or Microsoft toolchains.

License: MIT
