import asyncio
import logging

from asyncio.coroutines import iscoroutine

from .exceptions import (
    PacketInvalid,
    PacketInvalidSize,
    PacketInvalidType,
    SocketClosed,
)
from .read import (
    read_uint8,
    read_uint16,
)
from .source import Source

log = logging.getLogger(__name__)


class TCPProtocol(asyncio.Protocol):
    proxy_protocol = False
    PacketType = None
    PACKET_END = 0

    def __init__(self, callback_class):
        super().__init__()

        self._callback = callback_class

        self._data = b""
        self.new_connection = True

        self._queue = asyncio.Queue()
        self._can_write = asyncio.Event()
        self._can_write.set()

        self.task = asyncio.create_task(self._process_queue())

    def connection_made(self, transport):
        self.transport = transport
        # Ensure we start to use water-markers, as we want to know when the
        # peer is stalling. Without this, Python accepts any write you give
        # it by storing the data in an internal buffer. This is especially a
        # problem when transfering large files to the peer: if the peer
        # stalls, the memory of the application starts to grow significantly.
        self.transport.set_write_buffer_limits()

        socket_addr = transport.get_extra_info("peername")
        self.source = Source(self, socket_addr, socket_addr[0], socket_addr[1])

        if hasattr(self._callback, "connected"):
            self._callback.connected(self.source)

    def connection_lost(self, exc):
        if hasattr(self._callback, "disconnect"):
            self._callback.disconnect(self.source)
        self.task.cancel()

    async def _check_closed(self):
        while True:
            # When a peer is stalling, it can also mean the connection is
            # dropped on the other side. When this happens while we are
            # write-paused, we are not informed by asyncio the connection is
            # lost (connection_list() is not called yet). However,
            # is_closing() is already returning True.
            # So, when we are paused, we check every 5 seconds if is_closing()
            # is True. If so, we resume writing, and on the next write we
            # will pick up the connection is closing.
            # If we do not do this, these kind of connections are never
            # cleaned up properly.

            await asyncio.sleep(5)

            if self.transport.is_closing():
                self._can_write.set()
                return

    def pause_writing(self):
        self._can_write.clear()
        self._pause_task = asyncio.create_task(self._check_closed())

    def resume_writing(self):
        self._pause_task.cancel()
        self._can_write.set()

    def _detect_source_ip_port(self, data):
        if not self.proxy_protocol:
            return data

        # If enabled, expect new connections to start with PROXY. In this
        # header is the original source of the connection.
        if data[0:5] != b"PROXY":
            log.warning("Receive data without a proxy protocol header from %s:%d", self.source.ip, self.source.port)
            return data

        # This message arrived via the proxy protocol; use the information
        # from this to figure out the real ip and port.
        # Example how 'proxy' looks:
        #  PROXY TCP4 127.0.0.1 127.0.0.1 33487 12345

        # Search for \r\n, marking the end of the proxy protocol header.
        for i in range(len(data) - 1):
            if data[i] == 13 and data[i + 1] == 10:
                proxy_end = i
                break
        else:
            log.warning("Receive proxy protocol header without end from %s:%d", self.source.ip, self.source.port)
            return data

        proxy = data[0:proxy_end].tobytes().decode()
        (_, _, ip, _, port, _) = proxy.split(" ")
        self.source = Source(self, self.source.addr, ip, int(port))

        return data[proxy_end + 2 :]

    def data_received(self, data):
        data = memoryview(data)

        if self.new_connection:
            data = self._detect_source_ip_port(data)
            self.new_connection = False

        data = memoryview(self._data + data)
        self._data = self.receive_data(self._queue, data)

    def receive_data(self, queue, data):
        while len(data) > 2:
            length, _ = read_uint16(data)
            if length < 2:
                log.info(
                    "Dropping invalid packet from %s:%d: impossible length field of %d in packet",
                    self.source.ip,
                    self.source.port,
                    length,
                )
                self.transport.close()
                return b""

            if len(data) < length:
                break

            queue.put_nowait(data[0:length])
            data = data[length:]

        return data.tobytes()

    async def _process_queue(self):
        while True:
            data = await self._queue.get()

            try:
                packet_type, kwargs = self.receive_packet(self.source, data)
            except PacketInvalid as err:
                log.info("Dropping invalid packet from %s:%d: %r", self.source.ip, self.source.port, err)
                self.transport.close()
                return
            except asyncio.CancelledError:
                # Our coroutine is cancelled, pass it on the the caller.
                raise
            except Exception:
                log.exception("Internal error: receive_packet triggered an exception")
                self.transport.abort()
                return

            try:
                await getattr(self._callback, f"receive_{packet_type.name}")(self.source, **kwargs)
            except SocketClosed:
                # The other side is closing the connection; it can happen
                # there is still some writes in the buffer, so force a close
                # on our side too to free the resources.
                self.transport.abort()
                return
            except asyncio.CancelledError:
                # Our coroutine is cancelled, pass it on the the caller.
                raise
            except Exception:
                log.exception(f"Internal error: receive_{packet_type.name} triggered an exception")
                self.transport.abort()
                return

    def receive_packet(self, source, data):
        # Check length of packet
        length, data = read_uint16(data)
        if length != len(data) + 2:
            raise PacketInvalidSize(len(data) + 2, length)

        # Check if type is in range
        type, data = read_uint8(data)
        if type >= self.PACKET_END:
            raise PacketInvalidType(type)

        # Check if we expect this packet
        type = self.PacketType(type)
        func = getattr(self, f"receive_{type.name}", None)
        if func is None:
            raise PacketInvalidType(type)

        # Process this packet
        kwargs = func(source, data)
        return type, kwargs

    async def send_packet(self, data):
        await self._can_write.wait()

        # When a socket is closed on the other side, and due to the nature of
        # how asyncio is doing writes, we never receive an exception. So,
        # instead, check every time we send something if we are not closed.
        # If we are, inform our caller, which should cleanup the socket next.
        if self.transport.is_closing():
            raise SocketClosed

        res = self.transport.write(data)
        # For websockets, the return of the write is a coroutine. For
        # everything else, it is a non-blocking normal function.
        if iscoroutine(res):
            await res
