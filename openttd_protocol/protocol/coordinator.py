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
    write_bytes,
    write_init,
    write_presend,
    write_string,
    write_uint8,
    write_uint16,
    write_uint32,
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


class PacketCoordinatorType(enum.IntEnum):
    PACKET_COORDINATOR_GC_ERROR = 0
    PACKET_COORDINATOR_SERVER_REGISTER = 1
    PACKET_COORDINATOR_GC_REGISTER_ACK = 2
    PACKET_COORDINATOR_SERVER_UPDATE = 3
    PACKET_COORDINATOR_CLIENT_LISTING = 4
    PACKET_COORDINATOR_GC_LISTING = 5
    PACKET_COORDINATOR_CLIENT_CONNECT = 6
    PACKET_COORDINATOR_GC_CONNECTING = 7
    PACKET_COORDINATOR_SERCLI_CONNECT_FAILED = 8
    PACKET_COORDINATOR_GC_CONNECT_FAILED = 9
    PACKET_COORDINATOR_CLIENT_CONNECTED = 10
    PACKET_COORDINATOR_GC_DIRECT_CONNECT = 11
    PACKET_COORDINATOR_END = 12


class ServerGameType(enum.IntEnum):
    SERVER_GAME_TYPE_LOCAL = 0
    SERVER_GAME_TYPE_PUBLIC = 1
    SERVER_GAME_TYPE_END = 2


class ConnectionType(enum.IntEnum):
    CONNECTION_TYPE_UNKNOWN = 0
    CONNECTION_TYPE_ISOLATED = 1
    CONNECTION_TYPE_DIRECT = 2


class NetworkCoordinatorErrorType(enum.IntEnum):
    NETWORK_COORDINATOR_ERROR_UNKNOWN = 0
    NETWORK_COORDINATOR_ERROR_REGISTRATION_FAILED = 1
    NETWORK_COORDINATOR_ERROR_INVALID_INVITE_CODE = 2


class CoordinatorProtocol(TCPProtocol):
    PacketType = PacketCoordinatorType
    PACKET_END = PacketCoordinatorType.PACKET_COORDINATOR_END

    @staticmethod
    def receive_PACKET_COORDINATOR_SERVER_REGISTER(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version not in (1, 2):
            raise PacketInvalidData("unknown protocol version: ", protocol_version)

        game_type, data = read_uint8(data)

        if game_type >= ServerGameType.SERVER_GAME_TYPE_END:
            raise PacketInvalidData("invalid ServerGameType", game_type)

        game_type = ServerGameType(game_type)

        server_port, data = read_uint16(data)

        if protocol_version > 1:
            invite_code, data = read_string(data)
            invite_code_secret, data = read_string(data)
        else:
            invite_code = None
            invite_code_secret = None

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in SERVER_REGISTER; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "game_type": game_type,
            "server_port": server_port,
            "invite_code": invite_code,
            "invite_code_secret": invite_code_secret,
        }

    @staticmethod
    def receive_PACKET_COORDINATOR_SERVER_UPDATE(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version not in (1, 2):
            raise PacketInvalidData("unknown protocol version: ", protocol_version)

        game_info_version, data = read_uint8(data)

        if game_info_version < 1 or game_info_version > 4:
            raise PacketInvalidData("unknown game info version: ", game_info_version)

        if game_info_version >= 4:
            newgrf_count, data = read_uint8(data)

            newgrfs = []
            for i in range(newgrf_count):
                grfid, data = read_uint32(data)
                md5sum, data = read_bytes(data, 16)

                newgrfs.append({"grfid": grfid, "md5sum": md5sum.hex()})
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

            _, data = read_string(data)  # Unused, used to be map-name
            map_width, data = read_uint16(data)
            map_height, data = read_uint16(data)
            map_type, data = read_uint8(data)

            is_dedicated, data = read_uint8(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in SERVER_UPDATE; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
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
        }

    @staticmethod
    def receive_PACKET_COORDINATOR_CLIENT_LISTING(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version not in (1, 2):
            raise PacketInvalidData("unknown protocol version: ", len(protocol_version))

        game_info_version, data = read_uint8(data)

        if game_info_version < 1 or game_info_version > 4:
            raise PacketInvalidData("unknown game info version: ", game_info_version)

        openttd_version, data = read_string(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in CLIENT_LISTING; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "game_info_version": game_info_version,
            "openttd_version": openttd_version,
        }

    @staticmethod
    def receive_PACKET_COORDINATOR_CLIENT_CONNECT(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version != 2:
            raise PacketInvalidData("unknown protocol version: ", len(protocol_version))

        invite_code, data = read_string(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in CLIENT_CONNECT; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "invite_code": invite_code,
        }

    @staticmethod
    def receive_PACKET_COORDINATOR_SERCLI_CONNECT_FAILED(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version != 2:
            raise PacketInvalidData("unknown protocol version: ", len(protocol_version))

        token, data = read_string(data)
        tracking_number, data = read_uint8(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in SERCLI_CONNECT_FAILED; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "token": token,
            "tracking_number": tracking_number,
        }

    @staticmethod
    def receive_PACKET_COORDINATOR_CLIENT_CONNECTED(source, data):
        protocol_version, data = read_uint8(data)

        if protocol_version != 2:
            raise PacketInvalidData("unknown protocol version: ", len(protocol_version))

        token, data = read_string(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected in CLIENT_CONNECTED; remaining: ", len(data))

        return {
            "protocol_version": protocol_version,
            "token": token,
        }

    async def send_PACKET_COORDINATOR_GC_ERROR(self, protocol_version, error_no, error_detail):
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_ERROR)

        write_uint8(data, error_no.value)
        write_string(data, error_detail)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)

    async def send_PACKET_COORDINATOR_GC_REGISTER_ACK(
        self, protocol_version, connection_type, invite_code, invite_code_secret
    ):
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_REGISTER_ACK)

        if protocol_version > 1:
            write_string(data, invite_code)
            write_string(data, invite_code_secret)
        write_uint8(data, connection_type.value)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)

    async def send_PACKET_COORDINATOR_GC_LISTING(self, protocol_version, game_info_version, servers):
        for server in servers:
            if server.game_type != ServerGameType.SERVER_GAME_TYPE_PUBLIC:
                continue
            if len(server.info) == 0:
                continue

            data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_LISTING)

            write_uint16(data, 1)

            write_string(data, server.connection_string)
            write_uint8(data, game_info_version)

            if game_info_version >= 4:
                write_uint8(data, len(server.info["newgrfs"]))
                for newgrf in server.info["newgrfs"]:
                    write_uint32(data, newgrf["grfid"])
                    write_bytes(data, bytes.fromhex(newgrf["md5sum"]))

            if game_info_version >= 3:
                write_uint32(data, server.info["game_date"])
                write_uint32(data, server.info["start_date"])

            if game_info_version >= 2:
                write_uint8(data, server.info["companies_max"])
                write_uint8(data, server.info["companies_on"])
                write_uint8(data, server.info["spectators_max"])

            if game_info_version >= 1:
                write_string(data, server.info["name"])
                write_string(data, server.info["openttd_version"])
                write_uint8(data, 0)  # Unused, used to be server-lang
                write_uint8(data, server.info["use_password"])
                write_uint8(data, server.info["clients_max"])
                write_uint8(data, server.info["clients_on"])
                write_uint8(data, server.info["spectators_on"])

                if game_info_version < 3:
                    write_uint16(data, server.info["game_date"] - DAYS_TILL_ORIGINAL_BASE_YEAR)
                    write_uint16(data, server.info["start_date"] - DAYS_TILL_ORIGINAL_BASE_YEAR)

                write_string(data, "")  # Unused, used to be map-name
                write_uint16(data, server.info["map_width"])
                write_uint16(data, server.info["map_height"])
                write_uint8(data, server.info["map_type"])

                write_uint8(data, server.info["is_dedicated"])

            write_presend(data, SEND_TCP_MTU)
            await self.send_packet(data)

        # Send a final packet with 0 servers to indicate end-of-list.
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_LISTING)
        write_uint16(data, 0)
        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)

    async def send_PACKET_COORDINATOR_GC_CONNECTING(self, protocol_version, token, invite_code):
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_CONNECTING)

        write_string(data, token)
        write_string(data, invite_code)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)

    async def send_PACKET_COORDINATOR_GC_CONNECT_FAILED(self, protocol_version, token):
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_CONNECT_FAILED)

        write_string(data, token)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)

    async def send_PACKET_COORDINATOR_GC_DIRECT_CONNECT(self, protocol_version, token, tracking_number, hostname, port):
        data = write_init(PacketCoordinatorType.PACKET_COORDINATOR_GC_DIRECT_CONNECT)

        write_string(data, token)
        write_uint8(data, tracking_number)
        write_string(data, hostname)
        write_uint16(data, port)

        write_presend(data, SEND_TCP_MTU)
        await self.send_packet(data)
