import asyncio
import logging
from .event_emitter import EventEmitter
from .client import create_client, BedrockClient
from .server import create_server, BedrockServer, ServerClientConnection
logger = logging.getLogger(__name__)

class Relay(EventEmitter):

    def __init__(self, host: str='0.0.0.0', port: int=19132, destination_host: str='127.0.0.1', destination_port: int=19133):
        super().__init__()
        self.host = host
        self.port = port
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.server = create_server(host=host, port=port)
        self._setup_server_hooks()

    def _setup_server_hooks(self):

        @self.server.on('connect')
        def _on_client(session: ServerClientConnection):
            asyncio.create_task(self._bridge(session))

    async def _bridge(self, session: ServerClientConnection):
        remote = create_client(host=self.destination_host, port=self.destination_port)

        @remote.on('packet')
        def _ds_packet(pkt):
            self.emit('packet', {'direction': 'downstream', 'data': pkt})

        @session.on('packet')
        def _us_packet(pkt):
            self.emit('packet', {'direction': 'upstream', 'data': pkt})

        @session.on('disconnect')
        def _us_disconnect(reason):
            asyncio.create_task(remote.disconnect())
        try:
            await remote.connect()
        except Exception as exc:
            logger.error('Relay: failed to connect to %s:%d — %s', self.destination_host, self.destination_port, exc)

    async def start(self):
        await self.server.listen()

    def close(self):
        self.server.close()
