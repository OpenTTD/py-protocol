import enum
import logging

from ..wire.exceptions import PacketInvalidData
from ..wire.read import (
    read_bytes,
    read_string,
    read_uint8,
    read_uint16,
    read_uint32,
)
from ..wire.tcp import TCPProtocol
from ..wire.write import (
    SEND_TCP_MTU,
    write_init,
    write_presend,
)

log = logging.getLogger(__name__)


# The minimum starting year on the original TTD.
ORIGINAL_BASE_YEAR = 1920
# In GameInfo version 3 the date was changed to be counted from the year zero.
# This offset is added to version 2 and 1 to have the date the same for all
# versions. It is the amount of days from year 0 to 1920.
DAYS_TILL_ORIGINAL_BASE_YEAR = (
    365 * ORIGINAL_BASE_YEAR + ORIGINAL_BASE_YEAR // 4 - ORIGINAL_BASE_YEAR // 100 + ORIGINAL_BASE_YEAR // 400
)


class PacketGameType(enum.IntEnum):
    # TODO -- Packets 0 .. 5 are not implemented yet. Pull Requests are welcome.
    PACKET_SERVER_GAME_INFO = 6
    PACKET_CLIENT_GAME_INFO = 7
    # TODO -- Packets 8 .. 39 are not implemented yet. Pull Requests are welcome.
    PACKET_SERVER_SHUTDOWN = 40
    # TODO -- Packets 41 .. 43 are not implemented yet. Pull Requests are welcome.
    PACKET_END = 44


class NewGRFSerializationType(enum.IntEnum):
    NST_GRFID_MD5 = 0
    NST_GRFID_MD5_NAME = 1
    NST_LOOKUP_ID = 2
    NST_END = 3
    # NST_CONVERSION_GRFID_MD5 is an internal value, assigned for those servers that didn't send this value yet.
    NST_CONVERSION_GRFID_MD5 = 4


class GameProtocol(TCPProtocol):
    PacketType = PacketGameType
    PACKET_END = PacketGameType.PACKET_END

    @staticmethod
    def receive_PACKET_SERVER_GAME_INFO(source, data):
        game_info_version, data = read_uint8(data)

        if game_info_version < 1 or game_info_version > 6:
            raise PacketInvalidData("unknown game info version: ", game_info_version)

        if game_info_version >= 6:
            newgrf_serialization_type, data = read_uint8(data)

            if newgrf_serialization_type >= NewGRFSerializationType.NST_END:
                raise PacketInvalidData("invalid NewGRFSerializationType", newgrf_serialization_type)

            newgrf_serialization_type = NewGRFSerializationType(newgrf_serialization_type)
            if newgrf_serialization_type == NewGRFSerializationType.NST_LOOKUP_ID:
                raise PacketInvalidData("NewGRF serialization type cannot be NST_LOOKUP_ID")
        else:
            newgrf_serialization_type = NewGRFSerializationType.NST_CONVERSION_GRFID_MD5

        if game_info_version >= 5:
            gamescript_version, data = read_uint32(data)
            gamescript_name, data = read_string(data)
        else:
            gamescript_version = None
            gamescript_name = None

        if game_info_version >= 4:
            newgrf_count, data = read_uint8(data)

            newgrfs = []
            for _ in range(newgrf_count):
                grfid, data = read_uint32(data)
                md5sum, data = read_bytes(data, 16)

                if newgrf_serialization_type == NewGRFSerializationType.NST_GRFID_MD5_NAME:
                    name, data = read_string(data)
                else:
                    name = None

                newgrfs.append({"grfid": grfid, "md5sum": md5sum.hex(), "name": name})
        else:
            newgrfs = None

        if game_info_version >= 3:
            game_date, data = read_uint32(data)
            start_date, data = read_uint32(data)

        if game_info_version >= 2:
            companies_max, data = read_uint8(data)
            companies_on, data = read_uint8(data)
            spectators_max, data = read_uint8(data)
        else:
            companies_max = None
            companies_on = None
            spectators_max = None

        if game_info_version >= 1:
            name, data = read_string(data)
            openttd_version, data = read_string(data)
            if game_info_version < 6:
                _, data = read_uint8(data)  # Unused, used to be server-lang
            use_password, data = read_uint8(data)

            clients_max, data = read_uint8(data)
            clients_on, data = read_uint8(data)
            spectators_on, data = read_uint8(data)

            if game_info_version < 3:
                game_date, data = read_uint16(data)
                game_date += DAYS_TILL_ORIGINAL_BASE_YEAR
                start_date, data = read_uint16(data)
                start_date += DAYS_TILL_ORIGINAL_BASE_YEAR

            if game_info_version < 6:
                _, data = read_string(data)  # Unused, used to be map-name
            map_width, data = read_uint16(data)
            map_height, data = read_uint16(data)
            map_type, data = read_uint8(data)

            is_dedicated, data = read_uint8(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in SERVER_GAME_INFO; remaining: ", len(data))

        return {
            "newgrfs": newgrfs,
            "game_date": game_date,
            "start_date": start_date,
            "companies_max": companies_max,
            "companies_on": companies_on,
            "clients_max": clients_max,
            "clients_on": clients_on,
            "spectators_max": spectators_max,
            "spectators_on": spectators_on,
            "name": name,
            "openttd_version": openttd_version,
            "use_password": use_password,
            "is_dedicated": is_dedicated,
            "map_width": map_width,
            "map_height": map_height,
            "map_type": map_type,
            "gamescript_version": gamescript_version,
            "gamescript_name": gamescript_name,
        }

    @staticmethod
    def receive_PACKET_SERVER_SHUTDOWN(source, data):
        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in SERVER_SHUTDOWN; remaining: ", len(data))

        return {}

    async def send_PACKET_CLIENT_GAME_INFO(self):
        data = write_init(PacketGameType.PACKET_CLIENT_GAME_INFO)
        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)
