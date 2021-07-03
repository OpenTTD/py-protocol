import struct

from typing import Tuple

from .exceptions import PacketTooShort

# Two notes worth mentioning about this implementation:
#
# 1) This implementation uses try/except instead of length-checking. This has
#    as big adventage that the happy-flow is very fast. As disadventage is
#    that failures are much slower. But, as those are really rare, the total
#    speed improvement is significant.
#
# 2) This implementation uses a memoryview and not a class to be as quick as
#    possible without increasing the memory footprint by allocating another
#    object. This is not the most user-friendly way to work with this API, but
#    as it is running on the OpenTTD's backend to serve thousands of request
#    a day, speed / memory is an important consideration. As such, the API
#    suffers a bit under this constraint.


def read_uint8(data: memoryview) -> Tuple[int, memoryview]:
    """Read an uint8 from the data buffer."""
    try:
        value = struct.unpack_from("<B", data, 0)
    except struct.error:
        raise PacketTooShort from None
    return value[0], data[1:]


def read_uint16(data: memoryview) -> Tuple[int, memoryview]:
    """Read an uint16 from the data buffer."""
    try:
        value = struct.unpack_from("<H", data, 0)
    except struct.error:
        raise PacketTooShort from None
    return value[0], data[2:]


def read_uint32(data: memoryview) -> Tuple[int, memoryview]:
    """Read an uint32 from the data buffer."""
    try:
        value = struct.unpack_from("<I", data, 0)
    except struct.error:
        raise PacketTooShort from None
    return value[0], data[4:]


def read_uint64(data: memoryview) -> Tuple[int, memoryview]:
    """Read an uint64 from the data buffer."""
    try:
        value = struct.unpack_from("<Q", data, 0)
    except struct.error:
        raise PacketTooShort from None
    return value[0], data[8:]


def read_bytes(data: memoryview, length: int) -> Tuple[bytes, memoryview]:
    """Read length of bytes from the data buffer."""
    if len(data) < length:
        raise PacketTooShort
    return data[0:length].tobytes(), data[length:]


def read_string(data: memoryview) -> Tuple[str, memoryview]:
    """Read a (nul-terminated) string from the data buffer."""
    try:
        # We cannot used index() without converting it to a bytes first.
        # Given we use a memoryview to prevent copies being made all over the
        # place, that is rather unwanted. So, instead, look for the
        # nul-terminator manually.
        index = 0
        while data[index] != 0:
            index += 1
    except IndexError:
        raise PacketTooShort from None
    return data[0:index].tobytes().decode(), data[index + 1 :]
