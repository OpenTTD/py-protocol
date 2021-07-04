import asyncio
import enum
import pytest

from .exceptions import (
    PacketInvalidData,
    PacketInvalidSize,
    PacketInvalidType,
)
from .source import Source
from .tcp import TCPProtocol
from .read import read_uint8


class OpenTTDTestType(enum.Enum):
    PACKET_ONE = 0
    PACKET_TWO = 1
    PACKET_THREE = 2
    PACKET_END = 3


class OpenTTDProtocolTest(TCPProtocol):
    PacketType = OpenTTDTestType
    PACKET_END = PacketType.PACKET_END.value

    def receive_PACKET_ONE(self, source, data):
        assert data == b""
        return {}

    def receive_PACKET_TWO(self, source, data):
        value, data = read_uint8(data)

        if len(data) != 0:
            raise PacketInvalidData("more bytes than expected; remaining: ", len(data))

        return {"value": value}


class FakeTransport:
    def close(self):
        pass


@pytest.mark.parametrize(
    "proxy_protocol, data, result, ip, port",
    [
        (False, b"\x03\x00\x00", b"\x03\x00\x00", "127.0.0.2", 54321),
        (True, b"PROXY TCP4 127.0.0.1 127.0.0.1 12345 12121\r\n\x03\x00\x00", b"\x03\x00\x00", "127.0.0.1", 12345),
        (True, b"\x03\x00\x00", b"\x03\x00\x00", "127.0.0.2", 54321),
    ],
)
@pytest.mark.asyncio
async def test_detect_source_ip_port(proxy_protocol, data, result, ip, port):
    test = OpenTTDProtocolTest(None)
    test.task.cancel()
    test.source = Source(test, None, "127.0.0.2", 54321)
    test.proxy_protocol = proxy_protocol

    assert test._detect_source_ip_port(memoryview(data)) == result
    assert str(test.source.ip) == ip
    assert test.source.port == port


@pytest.mark.parametrize(
    "data, data_left, result",
    [
        (b"\x03\x00\x00", b"", b"\x03\x00\x00"),
        (b"\x03\x00\x00\x03", b"\x03", b"\x03\x00\x00"),
        (b"\x05\x00\x00", b"\x05\x00\x00", b""),
    ],
)
@pytest.mark.asyncio
async def test_data_received(data, data_left, result):
    test = OpenTTDProtocolTest(None)
    test.task.cancel()

    test.data_received(memoryview(data))
    assert test._data == data_left
    try:
        assert test._queue.get_nowait() == result
    except asyncio.queues.QueueEmpty:
        assert b"" == result


@pytest.mark.parametrize(
    "data, result",
    [
        (b"\x03\x00\x00", (OpenTTDTestType.PACKET_ONE, {})),
        (b"\x04\x00\x01\x02", (OpenTTDTestType.PACKET_TWO, {"value": 2})),
    ],
)
@pytest.mark.asyncio
async def test_receive_packet(data, result):
    test = OpenTTDProtocolTest(None)
    test.task.cancel()

    assert test.receive_packet(None, memoryview(data)) == result


@pytest.mark.parametrize(
    "data, failure",
    [
        (b"\x04\x00\x00", PacketInvalidSize),
        (b"\x03\x00\x02", PacketInvalidType),
        (b"\x03\x00\x03", PacketInvalidType),
        (b"\x05\x00\x01\x02\x00", PacketInvalidData),
    ],
)
@pytest.mark.asyncio
async def test_receive_packet_failure(data, failure):
    test = OpenTTDProtocolTest(None)
    test.task.cancel()

    with pytest.raises(failure):
        test.receive_packet(None, memoryview(data))


@pytest.mark.parametrize(
    "data, result",
    [
        (b"\x03\x00\x00", {}),
        (b"\x04\x00\x01\x02", {"value": 2}),
    ],
)
@pytest.mark.asyncio
async def test_process_queue(data, result):
    seen_packet = [False]

    class Callback:
        async def receive_PACKET_ONE(source, **kwargs):
            assert kwargs == result
            seen_packet[0] = True

        async def receive_PACKET_TWO(source, **kwargs):
            assert kwargs == result
            seen_packet[0] = True

    test = OpenTTDProtocolTest(Callback)
    test.task.cancel()

    test.source = Source(test, None, "127.0.0.1", 12345)
    test.transport = FakeTransport()

    test._queue.put_nowait(memoryview(data))
    test._queue.put_nowait(memoryview(b"\x04\x00\x00"))  # Force an exception
    await test._process_queue()
    assert seen_packet[0] is True
