from __future__ import print_function
from nose.tools import assert_equal, assert_in, assert_is


def assert_almost_equal(actual, expected, decimal=7, ctx=None):
    if hasattr(actual, "__iter__"):
        for a, e in zip(actual, expected):
            try:
                assert_almost_equal(a, e, decimal=decimal)
            except AssertionError as e:
                newmsg = "\n".join(["sequences are not almost equal:",
                                    "  actual:   " + str(actual),
                                    "  expected: " + str(expected),
                                    "because inner " + e.message])
                raise AssertionError(newmsg)

    else:
        diff = abs(actual - expected)
        maxdiff = 0.5 * 10**(-decimal)
        msg = "\n".join(["items are not almost equal up to %.e" % maxdiff,
                         "  actual:     " + str(actual),
                         "  expected:   " + str(expected),
                         "  difference: %.1e" % (diff)])
        assert diff < maxdiff, msg


import optirx as rx


def test_unpack_sender_data():
    with open("test/data/frame-000.bin", "rb") as f:
        binary = f.read()
        parsed = rx.unpack(binary)
        expected = rx.SenderData(appname=b"NatNetLib",
                                 version=(2,5,0,0),
                                 natnet_version=(2,5,0,0))
        print("parsed:\n",parsed)
        print("expected:\n",expected)
        assert_equal(parsed, expected)


def test_unpack_frame_of_data():

    expected_rb = [
        (-0.3015673756599426, 0.08478303998708725, 1.1143304109573364),
        (-0.23079043626785278, 0.04755447059869766, 1.1353150606155396),
        (-0.25711703300476074, -0.014958729967474937, 1.1209092140197754)]

    expected_om = [
        (-0.24560749530792236, 0.1687806248664856, 1.2753326892852783),
        (-0.11109362542629242, 0.1273186355829239, 1.2400494813919067)]

    for i in range(1,1+2):
        with open("test/data/frame-%03d.bin" % i, "rb") as f:
            binary = f.read()
            parsed = rx.unpack(binary)
            assert_is(type(parsed), rx.FrameOfData)
            assert_in(parsed.frameno, [92881, 92882])
            assert_in(b"all", parsed.sets)
            assert_in(b"Rigid Body 1", parsed.sets)
            assert_almost_equal(parsed.sets[b"Rigid Body 1"], expected_rb, 4)
            assert_equal(parsed.rigid_bodies[0].mrk_ids, (1,2,3))
            assert_equal(len(parsed.other_markers), 2)
            assert_almost_equal(parsed.other_markers, expected_om, 3)
            assert_equal(parsed.skeletons, [])
            assert_equal(len(parsed.labeled_markers), 3)
