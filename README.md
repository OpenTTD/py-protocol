# openttd-protocol

[![GitHub License](https://img.shields.io/github/license/OpenTTD/py-protocol)](https://github.com/OpenTTD/py-protocol/blob/main/LICENSE)
[![GitHub Tag](https://img.shields.io/github/v/tag/OpenTTD/py-protocol?include_prereleases&label=stable)](https://github.com/OpenTTD/py-protocol/releases)
[![GitHub commits since latest release](https://img.shields.io/github/commits-since/OpenTTD/py-protocol/latest/main)](https://github.com/OpenTTD/py-protocol/commits/main)

[![GitHub Workflow Status (Testing)](https://img.shields.io/github/workflow/status/OpenTTD/py-protocol/Testing/main?label=main)](https://github.com/OpenTTD/py-protocol/actions?query=workflow%3ATesting)
[![GitHub Workflow Status (Release)](https://img.shields.io/github/workflow/status/OpenTTD/py-protocol/Release?label=release)](https://github.com/OpenTTD/py-protocol/actions?query=workflow%3A%22Release%22)

This library implements the OpenTTD network protocol.
It mostly is meant to be used for OpenTTD's backend services, like [BaNaNaS server](https://github.com/OpenTTD/bananas-server) and [master server](https://github.com/OpenTTD/master-server).

# Usage

`pip install openttd-protocol`

Now in your Python code you can import the protocol.
Example:

```python
import asyncio
import logging

from openttd_protocol.protocol.coordinator import CoordinatorProtocol

log = logging.getLogger(__name__)


class Application:
    async def receive_PACKET_COORDINATOR_CLIENT_REGISTER(self, source, protocol_version, game_type, server_port):
        # Your logic goes here
        pass


def main():
    application = Application()

    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(loop.create_server(lambda: CoordinatorProtocol(application), host="127.0.0.1", port=12345, reuse_port=True, start_serving=True))

    try:
        loop.run_until_complete(server.serve_forever())
    except KeyboardInterrupt:
        pass

    log.info("Shutting down game_coordinator ...")
    server.close()

if __name__ == "__main__":
    main()
```
