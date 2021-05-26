import ipaddress


class Source:
    def __init__(self, protocol, addr, ip, port):
        self.protocol = protocol
        self.addr = addr

        # Normally ip and port are in addr, but in case of Proxy Protocol
        # this might differ. So, please use ip/port over addr.
        self.ip = ipaddress.ip_address(ip)
        self.port = port

        # If using IPv6, IPv4 addresses are mapped like "::fffff:<IPv4>".
        # Convert those instances to an IPv4Address, so the class of an
        # instance can be used to easily detect if it is an IPv4 or IPv6.
        if isinstance(self.ip, ipaddress.IPv6Address) and self.ip.ipv4_mapped:
            self.ip = self.ip.ipv4_mapped

    def __repr__(self):
        return f"Source(ip={self.ip!r}, port={self.port!r}, addr={self.addr!r})"
