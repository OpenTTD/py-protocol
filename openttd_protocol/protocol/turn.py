import enum
import logging

from ..wire.exceptions import PacketInvalidData
from ..wire.read import (
    read_string,
    read_uint8,
)
from ..wire.tcp import TCPProtocol
from ..wire.write import (
    SEND_TCP_MTU,
    write_init,
    write_presend,
    write_string,
)

log = logging.getLogger(__name__)


class PacketTurnType(enum.IntEnum):
    PACKET_TURN_TURN_ERROR = 0
    PACKET_TURN_SERCLI_CONNECT = 1
    PACKET_TURN_TURN_CONNECTED = 2
    PACKET_TURN_END = 3


class TurnProtocol(TCPProtocol):
    PacketType = PacketTurnType
    PACKET_END = PacketTurnType.PACKET_TURN_END

    @staticmethod
    def receive_PACKET_TURN_SERCLI_CONNECT(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version < 5 or protocol_version > 6:
            raise PacketInvalidData("unknown protocol version: ", protocol_version)

        ticket, data = read_string(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"protocol_version": protocol_version, "ticket": ticket}

    async def send_PACKET_TURN_TURN_CONNECTED(self, protocol_version, hostname):
        data = write_init(PacketTurnType.PACKET_TURN_TURN_CONNECTED)

        write_string(data, hostname)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)
