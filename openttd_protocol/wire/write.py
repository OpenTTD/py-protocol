import struct

from .exceptions import PacketTooBig

SEND_TCP_MTU = 32767
SEND_UDP_MTU = 1460


def write_uint8(data: bytearray, value: int) -> None:
    """Write a uint8 in the packet."""
    data += struct.pack("<B", value)


def write_uint16(data: bytearray, value: int) -> None:
    """Write a uint16 in the packet."""
    data += struct.pack("<H", value)


def write_uint32(data: bytearray, value: int) -> None:
    """Write a uint32 in the packet."""
    data += struct.pack("<I", value)


def write_uint64(data: bytearray, value: int) -> None:
    """Write a uint64 in the packet."""
    data += struct.pack("<Q", value)


def write_string(data: bytearray, value: str) -> None:
    """Write a string in the packet."""
    data += value.encode() + b"\x00"


def write_init(type: int) -> bytearray:
    """Initialize the writing of a new packet."""
    # write_presend() will replace this with the length of the packet.
    data = bytearray(b"\x00\x00")
    write_uint8(data, type)

    return data


def write_presend(data: bytearray, max_size: int = SEND_TCP_MTU) -> bytes:
    """Prepare a packet for sending. Returns an immutable list of bytes to send."""
    if len(data) > max_size:
        raise PacketTooBig(len(data))

    data[0:2] = struct.pack("<H", len(data))
    return bytes(data)
