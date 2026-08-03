import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from .config import BotConfig
from .client import BedrockClient
from .event_emitter import EventEmitter
logger = logging.getLogger(__name__)

@dataclass
class BotStats:
    start_time: float = field(default_factory=time.monotonic)
    connect_time: float | None = None
    messages_received: int = 0
    packets_received: int = 0
    reconnect_count: int = 0
    last_error: str = ''

    @property
    def uptime(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def session_time(self) -> float | None:
        if self.connect_time is None:
            return None
        return time.monotonic() - self.connect_time

    def to_dict(self) -> dict:
        return {'uptime_s': round(self.uptime, 1), 'session_s': round(self.session_time, 1) if self.session_time else None, 'messages_received': self.messages_received, 'packets_received': self.packets_received, 'reconnect_count': self.reconnect_count, 'last_error': self.last_error}

class Bot(EventEmitter):

    def __init__(self, host: str, port: int, *, config: BotConfig | None=None):
        super().__init__()
        self.host = host
        self.port = port
        self.config: BotConfig = config or BotConfig()
        self.stats = BotStats()
        self._chat_history: deque[dict[str, Any]] = deque(maxlen=self.config.chat_history_size)
        self._client: BedrockClient | None = None
        self._stopped = False
        self._disconnected = asyncio.Event()
        self._chat_file_logger: logging.Logger | None = None
        self._autosave_task: asyncio.Task | None = None
        self._setup_logging()

    def _setup_logging(self):
        cfg = self.config
        level = getattr(logging, cfg.log_level.upper(), logging.INFO) if isinstance(cfg.log_level, str) else cfg.log_level
        lib_logger = logging.getLogger('r_python_bedrock_protocol')
        lib_logger.setLevel(level)
        if not lib_logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(level)
            ch.setFormatter(logging.Formatter(cfg.log_format, cfg.log_date_format))
            lib_logger.addHandler(ch)
        if cfg.log_file:
            fh = logging.FileHandler(cfg.log_file, encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(cfg.log_format, cfg.log_date_format))
            lib_logger.addHandler(fh)
        if cfg.chat_log_file:
            self._chat_file_logger = logging.getLogger('r_python_bedrock_protocol.chat')
            self._chat_file_logger.setLevel(logging.DEBUG)
            self._chat_file_logger.propagate = False
            if not self._chat_file_logger.handlers:
                cfh = logging.FileHandler(cfg.chat_log_file, encoding='utf-8')
                cfh.setFormatter(logging.Formatter(cfg.chat_log_format, cfg.log_date_format))
                self._chat_file_logger.addHandler(cfh)

    @property
    def chat_history(self) -> list[dict[str, Any]]:
        return list(self._chat_history)

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client._raknet is not None and self._client._raknet.connected

    async def start(self):
        self._stopped = False
        await self._do_connect()

    async def run(self):
        self._stopped = False
        reconnect_count = 0
        delay = self.config.reconnect_delay
        while not self._stopped:
            self._disconnected.clear()
            try:
                logger.info('Connecting to %s:%d  version=%s  device=%s  username=%s', self.host, self.port, self.config.version, self.config.device, self.config.username)
                await self._do_connect()
                self.stats.connect_time = time.monotonic()
                delay = self.config.reconnect_delay
                await self._disconnected.wait()
            except asyncio.TimeoutError:
                err = f'Connection timed out ({self.config.connect_timeout}s)'
                logger.error(err)
                self.stats.last_error = err
                self.emit('error', TimeoutError(err))
            except OSError as exc:
                err = f'Network error: {exc}'
                logger.error(err)
                self.stats.last_error = err
                self.emit('error', exc)
            except Exception as exc:
                err = f'Unexpected error: {exc}'
                logger.error(err, exc_info=True)
                self.stats.last_error = err
                self.emit('error', exc)
            if self._stopped:
                break
            if not self.config.auto_reconnect:
                break
            max_r = self.config.max_reconnects
            if 0 <= max_r <= reconnect_count:
                logger.warning('Max reconnects (%d) reached. Stopping.', max_r)
                break
            reconnect_count += 1
            self.stats.reconnect_count = reconnect_count
            logger.info('Reconnecting in %.1fs (attempt %d)…', delay, reconnect_count)
            self.emit('reconnecting', {'attempt': reconnect_count, 'delay': delay})
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, self.config.reconnect_delay_max)
        logger.info('Bot stopped.')
        self.emit('stopped')

    async def stop(self):
        self._stopped = True
        if self._autosave_task:
            self._autosave_task.cancel()
        if self._client:
            await self._client.disconnect()
        self._disconnected.set()

    async def send_message(self, message: str, delay: float=0):
        if delay > 0:
            await asyncio.sleep(delay)
        if self._client:
            self._client.send('text', {'message': message})
            logger.debug('→ chat: %s', message)

    def send_command(self, command: str):
        if self._client:
            self._client.send('command', {'command': command})
            logger.debug('→ command: %s', command)

    def save_chat(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        logger.info('Chat history saved to %s (%d messages)', path, len(self._chat_history))

    def clear_chat(self):
        self._chat_history.clear()

    async def _do_connect(self):
        self._client = BedrockClient(self.host, self.port, config=self.config)
        self._wire_events()
        await self._client.connect(timeout=self.config.connect_timeout)
        if self.config.chat_autosave_file:
            self._autosave_task = asyncio.create_task(self._autosave_loop())

    def _wire_events(self):
        c = self._client

        @c.on('connect')
        def _connect():
            logger.info('RakNet connected to %s:%d', self.host, self.port)
            self.emit('connect')

        @c.on('spawn')
        def _spawn():
            logger.info('Login accepted — loading world…')
            self.emit('spawn')

        @c.on('start_game')
        def _start_game(data):
            spawn = data.get('spawn', (0, 0, 0))
            logger.info('StartGame — gamemode=%s  spawn=%.1f,%.1f,%.1f', data.get('player_gamemode', '?'), *spawn)
            self.emit('start_game', data)

        @c.on('join')
        def _join():
            logger.info('Joined world! (session uptime: %.1fs)', self.stats.uptime)
            self.stats.connect_time = time.monotonic()
            self.emit('join')

        @c.on('text')
        def _text(pkt: dict):
            self.stats.messages_received += 1
            src = pkt.get('source_name', '')
            msg = pkt.get('message', '')
            entry = {'ts': time.time(), 'source': src, 'message': msg, 'type': pkt.get('type', 0)}
            self._chat_history.append(entry)
            if src:
                logger.info('chat  <%s> %s', src, msg)
            else:
                logger.info('chat  %s', msg)
            if self._chat_file_logger:
                line = f'<{src}> {msg}' if src else msg
                self._chat_file_logger.info(line)
            if self.config.on_chat:
                try:
                    self.config.on_chat(entry)
                except Exception as exc:
                    logger.error('on_chat callback error: %s', exc)
            self.emit('text', pkt)
            self.emit('chat', entry)

        @c.on('packet')
        def _packet(pkt):
            self.stats.packets_received += 1
            self.emit('packet', pkt)

        @c.on('disconnect')
        def _disconnect(reason: str):
            logger.info('Disconnected from server: %s', reason or '(no reason given)')
            self.emit('disconnect', reason)
            self._disconnected.set()

        @c.on('transfer')
        def _transfer(info):
            logger.info('Server transfer → %s:%d', info['host'], info['port'])
            self.emit('transfer', info)

        @c.on('error')
        def _error(exc: Exception):
            self.stats.last_error = str(exc)
            logger.error('Client error: %s', exc)
            self.emit('error', exc)

        @c.on('close')
        def _close():
            self.emit('close')
            self._disconnected.set()

        @c.on('network_settings')
        def _net(info):
            self.emit('network_settings', info)

    async def _autosave_loop(self):
        path = self.config.chat_autosave_file
        interval = max(5, self.config.chat_autosave_interval)
        while True:
            await asyncio.sleep(interval)
            if self._chat_history:
                try:
                    self.save_chat(path)
                except Exception as exc:
                    logger.warning('Chat autosave failed: %s', exc)

    def __repr__(self) -> str:
        status = 'connected' if self.is_connected else 'disconnected'
        return f'<Bot {self.config.username}@{self.host}:{self.port} v={self.config.version} {status}>'

class BotCluster(EventEmitter):

    def __init__(self):
        super().__init__()
        self.bots: list[Bot] = []

    def add_bot(self, bot: Bot) -> Bot:
        self.bots.append(bot)
        return bot

    @classmethod
    def create_swarm(cls, host: str, port: int, *, names: list[str] | None=None, prefix: str='Bot_', count: int=2, config_template: BotConfig | None=None) -> 'BotCluster':
        cluster = cls()
        template = config_template or BotConfig()
        bot_names = names if names else [f'{prefix}{i+1}' for i in range(count)]
        for name in bot_names:
            cfg = BotConfig(username=name, device=template.device, device_model=template.device_model, device_id=template.device_id, version=template.version, offline=template.offline, auto_reconnect=template.auto_reconnect, reconnect_delay=template.reconnect_delay, reconnect_delay_max=template.reconnect_delay_max, max_reconnects=template.max_reconnects, connect_timeout=template.connect_timeout, log_level=template.log_level, log_file=template.log_file, chat_log_file=template.chat_log_file, log_packets=template.log_packets, chat_history_size=template.chat_history_size, chat_autosave_file=template.chat_autosave_file, chat_autosave_interval=template.chat_autosave_interval, join_delay=template.join_delay, chunk_radius=template.chunk_radius, auto_resource_packs=template.auto_resource_packs, respond_tick_sync=template.respond_tick_sync, on_chat=template.on_chat)
            bot = Bot(host, port, config=cfg)
            cluster.add_bot(bot)
        return cluster

    async def run_all(self):
        if not self.bots:
            return
        await asyncio.gather(*[bot.run() for bot in self.bots], return_exceptions=True)

    async def start_all(self):
        if not self.bots:
            return
        await asyncio.gather(*[bot.start() for bot in self.bots], return_exceptions=True)

    async def stop_all(self):
        if not self.bots:
            return
        await asyncio.gather(*[bot.stop() for bot in self.bots], return_exceptions=True)

    async def broadcast(self, message: str, delay: float=0):
        for bot in self.bots:
            if bot.is_connected:
                await bot.send_message(message, delay=delay)

    def on_all(self, event_name: str, handler):
        for bot in self.bots:
            bot.on(event_name, handler)

    @property
    def stats(self) -> list[dict]:
        return [bot.stats.to_dict() for bot in self.bots]

