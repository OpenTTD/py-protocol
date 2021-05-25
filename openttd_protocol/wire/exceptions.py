class PacketInvalid(Exception):
    """There was an error with this packet. This is a base exception."""


class PacketInvalidSize(PacketInvalid):
    """The size of this packet is not as announced."""


class PacketInvalidType(PacketInvalid):
    """The type of this packet is not valid."""


class PacketTooBig(PacketInvalid):
    """The packet is too big to transmit."""


class PacketTooShort(PacketInvalid):
    """The packet was expected to contain more data than it actually does."""


class PacketInvalidData(PacketInvalid):
    """The packet contains invalid data."""


class SocketClosed(Exception):
    """The socket was closed by the other side."""
