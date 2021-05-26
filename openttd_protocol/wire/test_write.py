import pytest

from .exceptions import PacketTooBig
from .write import (
    SEND_TCP_MTU,
    write_bytes,
    write_init,
    write_presend,
    write_string,
    write_uint16,
    write_uint32,
    write_uint64,
    write_uint8,
)


@pytest.mark.parametrize(
    "proc, value, result",
    [
        (write_uint8, 1, b"\x01"),
        (write_uint16, 0x0201, b"\x01\x02"),
        (write_uint32, 0x04030201, b"\x01\x02\x03\x04"),
        (write_uint64, 0x0807060504030201, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
        (write_bytes, b"\x01\x02", b"\x01\x02"),
        (write_string, "abc", b"abc\x00"),
    ],
)
def test_write(proc, value, result):
    data = write_init(1)
    proc(data, value)

    assert data == b"\x00\x00\x01" + result


def test_write_presend():
    data = write_init(1)
    write_uint32(data, 0)
    packet = write_presend(data, SEND_TCP_MTU)

    assert packet == b"\x07\x00\x01\x00\x00\x00\x00"

    # Test with the indicated payload too.
    with pytest.raises(PacketTooBig):
        write_presend(data, 1)
