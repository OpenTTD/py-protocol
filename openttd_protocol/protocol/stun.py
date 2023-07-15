import enum
import logging

from ..wire.exceptions import PacketInvalidData
from ..wire.read import (
    read_string,
    read_uint8,
)
from ..wire.tcp import TCPProtocol

log = logging.getLogger(__name__)


class PacketStunType(enum.IntEnum):
    PACKET_STUN_SERCLI_STUN = 0
    PACKET_STUN_END = 1


class StunProtocol(TCPProtocol):
    PacketType = PacketStunType
    PACKET_END = PacketStunType.PACKET_STUN_END

    @staticmethod
    def receive_PACKET_STUN_SERCLI_STUN(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version < 3 or protocol_version > 6:
            raise PacketInvalidData("unknown protocol version: ", protocol_version)

        token, data = read_string(data)
        interface_number, data = read_uint8(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "token": token,
            "interface_number": interface_number,
        }
