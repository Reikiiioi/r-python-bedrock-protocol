import asyncio
import time
import struct
from dataclasses import dataclass
from .raknet.protocol import RAKNET_MAGIC, ID_UNCONNECTED_PING

@dataclass
class ServerAdvertisement:
    edition: str
    motd: str
    protocol_version: int
    version: str
    players_online: int
    players_max: int
    server_id: str
    sub_motd: str
    game_mode: str

    @classmethod
    def from_string(cls, data_str: str) -> 'ServerAdvertisement':
        parts = data_str.split(';')
        return cls(edition=parts[0] if len(parts) > 0 else 'MCPE', motd=parts[1] if len(parts) > 1 else '', protocol_version=int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0, version=parts[3] if len(parts) > 3 else '', players_online=int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0, players_max=int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0, server_id=parts[6] if len(parts) > 6 else '', sub_motd=parts[7] if len(parts) > 7 else '', game_mode=parts[8] if len(parts) > 8 else 'Survival')

class PingProtocol(asyncio.DatagramProtocol):

    def __init__(self, ping_id: int):
        self.ping_id = ping_id
        self.future = asyncio.Future()

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if not data or data[0] != 28:
            return
        if len(data) > 35:
            length = struct.unpack_from('>H', data, 33)[0]
            adv_str = data[35:35 + length].decode('utf-8', errors='ignore')
            if not self.future.done():
                self.future.set_result(ServerAdvertisement.from_string(adv_str))

async def ping(host: str, port: int=19132, timeout: float=5.0) -> ServerAdvertisement:
    loop = asyncio.get_running_loop()
    ping_time = int(time.time() * 1000)
    protocol = PingProtocol(ping_time)
    transport, _ = await loop.create_datagram_endpoint(lambda: protocol, remote_addr=(host, port))
    try:
        packet = bytearray()
        packet.append(ID_UNCONNECTED_PING)
        packet.extend(struct.pack('>q', ping_time))
        packet.extend(RAKNET_MAGIC)
        packet.extend(struct.pack('>q', 1311768467463790320))
        transport.sendto(bytes(packet))
        return await asyncio.wait_for(protocol.future, timeout=timeout)
    finally:
        transport.close()
