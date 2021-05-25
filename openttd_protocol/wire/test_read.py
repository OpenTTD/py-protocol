import pytest

from .exceptions import PacketTooShort
from .read import (
    read_uint8,
    read_uint16,
    read_uint32,
    read_uint64,
    read_bytes,
    read_string,
)


@pytest.mark.parametrize(
    "proc, data, result1, result2",
    [
        (read_uint8, b"\x00\x01", 0, 1),
        (read_uint16, b"\x00\x00\x01\x02", 0, 0x0201),
        (read_uint32, b"\x00\x00\x00\x00\x01\x02\x03\x04", 0, 0x04030201),
        (read_uint64, b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08", 0, 0x0807060504030201),
        (lambda data: read_bytes(data, 2), b"\x00\x00\x01\x02", b"\x00\x00", b"\x01\x02"),
        (read_string, b"abc\x00def\x00", "abc", "def"),
    ],
)
def test_read(proc, data, result1, result2):
    data = memoryview(data)

    value, data = proc(data)
    assert value == result1

    value, data = proc(data)
    assert value == result2


@pytest.mark.parametrize(
    "proc, data",
    [
        (read_uint8, b""),
        (read_uint16, b"\x00"),
        (read_uint32, b"\x00\x00\x00"),
        (read_uint64, b"\x00\x00\x00\x00\x00\x00\x00"),
        (lambda data: read_bytes(data, 2), b"\x00"),
        (read_string, b"ab"),
    ],
)
def test_read_failure(proc, data):
    data = memoryview(data)

    # Empty should always result in an error.
    with pytest.raises(PacketTooShort):
        proc(memoryview(b""))

    # Test with the indicated payload too.
    with pytest.raises(PacketTooShort):
        proc(data)
