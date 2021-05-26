import enum
import logging
import struct

from ..wire.exceptions import PacketInvalidData
from ..wire.read import (
    read_uint8,
    read_uint16,
    read_uint32,
)
from ..wire.tcp import TCPProtocol
from ..wire.write import (
    SEND_TCP_COMPAT_MTU,
    write_init,
    write_presend,
    write_string,
    write_uint8,
    write_uint32,
)

log = logging.getLogger(__name__)


# Copy from OpenTTD/src/network/core/tcp_content.h
class PacketContentType(enum.IntEnum):
    PACKET_CONTENT_CLIENT_INFO_LIST = 0
    PACKET_CONTENT_CLIENT_INFO_ID = 1
    PACKET_CONTENT_CLIENT_INFO_EXTID = 2
    PACKET_CONTENT_CLIENT_INFO_EXTID_MD5 = 3
    PACKET_CONTENT_SERVER_INFO = 4
    PACKET_CONTENT_CLIENT_CONTENT = 5
    PACKET_CONTENT_SERVER_CONTENT = 6
    PACKET_CONTENT_END = 7


class ContentType(enum.IntEnum):
    CONTENT_TYPE_BASE_GRAPHICS = 1
    CONTENT_TYPE_NEWGRF = 2
    CONTENT_TYPE_AI = 3
    CONTENT_TYPE_AI_LIBRARY = 4
    CONTENT_TYPE_SCENARIO = 5
    CONTENT_TYPE_HEIGHTMAP = 6
    CONTENT_TYPE_BASE_SOUNDS = 7
    CONTENT_TYPE_BASE_MUSIC = 8
    CONTENT_TYPE_GAME = 9
    CONTENT_TYPE_GAME_LIBRARY = 10
    CONTENT_TYPE_END = 11


class ContentInfo:
    def __init__(self, content_id=None, content_type=None, unique_id=None, md5sum=None):
        super().__init__()

        self.content_id = content_id
        self.content_type = content_type
        self.unique_id = unique_id
        self.md5sum = md5sum

    def __repr__(self):
        return (
            f"ContentInfo(content_id={self.content_id!r},"
            f"content_type={self.content_type!r}, "
            f"unique_id={self.unique_id!r}, "
            f"md5sum={self.md5sum!r})"
        )


class ContentProtocol(TCPProtocol):
    PacketType = PacketContentType
    PACKET_END = PacketContentType.PACKET_CONTENT_END

    @staticmethod
    def receive_PACKET_CONTENT_CLIENT_INFO_LIST(source, data):
        content_type, data = read_uint8(data)
        openttd_version, data = read_uint32(data)

        if content_type >= ContentType.CONTENT_TYPE_END:
            raise PacketInvalidData("invalid ContentType", content_type)

        content_type = ContentType(content_type)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"content_type": content_type, "openttd_version": openttd_version}

    @staticmethod
    def _receive_client_info(data, count, has_content_id=False, has_content_type_and_unique_id=False, has_md5sum=False):
        content_infos = []
        for _ in range(count):
            content_info = {}

            if has_content_id:
                content_id, data = read_uint32(data)
                content_info["content_id"] = content_id

            if has_content_type_and_unique_id:
                content_type, data = read_uint8(data)
                if content_type >= ContentType.CONTENT_TYPE_END:
                    raise PacketInvalidData("invalid ContentType", content_type)
                content_type = ContentType(content_type)
                content_info["content_type"] = content_type

                unique_id, data = read_uint32(data)
                if content_type == ContentType.CONTENT_TYPE_NEWGRF:
                    # OpenTTD client sends NewGRFs byte-swapped for some reason.
                    # So we swap it back here, as nobody needs to know the
                    # protocol is making a boo-boo.
                    content_info["unique_id"] = unique_id.to_bytes(4, "big")
                elif content_type in (ContentType.CONTENT_TYPE_SCENARIO, ContentType.CONTENT_TYPE_HEIGHTMAP):
                    # We store Scenarios / Heightmaps byte-swapped (to what OpenTTD expects).
                    # This is because otherwise folders are named 01000000, 02000000, which
                    # makes sorting a bit odd, and in general just difficult to read.
                    content_info["unique_id"] = unique_id.to_bytes(4, "big")
                else:
                    content_info["unique_id"] = unique_id.to_bytes(4, "little")

            if has_md5sum:
                md5sum = bytearray()
                for _ in range(16):
                    md5sum_snippet, data = read_uint8(data)
                    md5sum.append(md5sum_snippet)
                md5sum = bytes(md5sum)
                content_info["md5sum"] = md5sum

            content_infos.append(ContentInfo(**content_info))

        return content_infos, data

    @classmethod
    def receive_PACKET_CONTENT_CLIENT_INFO_ID(cls, source, data):
        count, data = read_uint16(data)

        content_infos, data = cls._receive_client_info(data, count, has_content_id=True)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"content_infos": content_infos}

    @classmethod
    def receive_PACKET_CONTENT_CLIENT_INFO_EXTID(cls, source, data):
        count, data = read_uint8(data)

        content_infos, data = cls._receive_client_info(data, count, has_content_type_and_unique_id=True)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"content_infos": content_infos}

    @classmethod
    def receive_PACKET_CONTENT_CLIENT_INFO_EXTID_MD5(cls, source, data):
        count, data = read_uint8(data)

        content_infos, data = cls._receive_client_info(
            data, count, has_content_type_and_unique_id=True, has_md5sum=True
        )

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"content_infos": content_infos}

    @classmethod
    def receive_PACKET_CONTENT_CLIENT_CONTENT(cls, source, data):
        count, data = read_uint16(data)

        content_infos, data = cls._receive_client_info(data, count, has_content_id=True)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"content_infos": content_infos}

    async def send_PACKET_CONTENT_SERVER_INFO(
        self, content_type, content_id, filesize, name, version, url, description, unique_id, md5sum, dependencies, tags
    ):
        data = write_init(PacketContentType.PACKET_CONTENT_SERVER_INFO)

        write_uint8(data, content_type.value)
        write_uint32(data, content_id)

        write_uint32(data, filesize)
        write_string(data, name)
        write_string(data, version)
        write_string(data, url)
        write_string(data, description)

        if content_type == ContentType.CONTENT_TYPE_NEWGRF:
            # OpenTTD client sends NewGRFs byte-swapped for some reason.
            # So we swap it back here, as nobody needs to know the
            # protocol is making a boo-boo.
            write_uint32(data, struct.unpack(">I", unique_id)[0])
        elif content_type in (ContentType.CONTENT_TYPE_SCENARIO, ContentType.CONTENT_TYPE_HEIGHTMAP):
            # We store Scenarios / Heightmaps byte-swapped (to what OpenTTD expects).
            # This is because otherwise folders are named 01000000, 02000000, which
            # makes sorting a bit odd, and in general just difficult to read.
            write_uint32(data, struct.unpack(">I", unique_id)[0])
        else:
            write_uint32(data, struct.unpack("<I", unique_id)[0])

        for i in range(16):
            write_uint8(data, md5sum[i])

        write_uint8(data, len(dependencies))
        for dependency in dependencies:
            write_uint32(data, dependency)

        write_uint8(data, len(tags))
        for tag in tags:
            write_string(data, tag)

        write_presend(data, SEND_TCP_COMPAT_MTU)
        await self.send_packet(data)

    async def send_PACKET_CONTENT_SERVER_CONTENT(self, content_type, content_id, filesize, filename, stream):
        # First, send a packet to tell the client it will be receiving a file
        data = write_init(PacketContentType.PACKET_CONTENT_SERVER_CONTENT)

        write_uint8(data, content_type.value)
        write_uint32(data, content_id)

        write_uint32(data, filesize)
        write_string(data, filename)

        write_presend(data, SEND_TCP_COMPAT_MTU)
        await self.send_packet(data)

        # Next, send the content of the file over
        while not stream.eof():
            data = write_init(PacketContentType.PACKET_CONTENT_SERVER_CONTENT)
            data += stream.read(SEND_TCP_COMPAT_MTU - 3)
            write_presend(data, SEND_TCP_COMPAT_MTU)
            await self.send_packet(data)

        write_init(PacketContentType.PACKET_CONTENT_SERVER_CONTENT)
        write_presend(data, SEND_TCP_COMPAT_MTU)
        await self.send_packet(data)
