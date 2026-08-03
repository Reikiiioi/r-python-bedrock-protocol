import uuid
import logging
from dataclasses import dataclass, field
from typing import Callable
from .protocol.versions import LATEST_VERSION
from .protocol.devices import DEFAULT_DEVICE

def _gen_uuid() -> str:
    return str(uuid.uuid4())

@dataclass
class SkinConfig:
    data: bytes | None = None
    skin_id: str = 'Steve'
    width: int = 64
    height: int = 64
    cape_data: str = ''
    cape_id: str = ''
    cape_on_classic: bool = False
    arm_size: str = 'wide'
    is_persona: bool = False
    persona_pieces: list = field(default_factory=list)
    resource_patch: str | None = None

@dataclass
class BotConfig:
    username: str = 'Steve'
    player_uuid: str | None = None
    xuid: str = ''
    language_code: str = 'en_US'
    device: str = DEFAULT_DEVICE
    device_model: str | None = None
    device_id: str | None = None
    client_random_id: int | None = None
    http_user_agent: str = 'MCPE/Android'
    gui_scale: int = 0
    title_id: str = '896928775'
    skin: SkinConfig = field(default_factory=SkinConfig)
    version: str | int = LATEST_VERSION
    offline: bool = True
    connect_timeout: float = 10.0
    mtu: int = 1400
    auto_reconnect: bool = False
    reconnect_delay: float = 3.0
    reconnect_delay_max: float = 60.0
    max_reconnects: int = -1
    log_level: str | int = 'INFO'
    log_file: str | None = None
    log_format: str = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    log_date_format: str = '%Y-%m-%d %H:%M:%S'
    chat_log_file: str | None = None
    chat_log_format: str = '%(asctime)s | %(message)s'
    log_packets: bool = False
    chat_history_size: int = 2000
    chat_autosave_file: str | None = None
    chat_autosave_interval: int = 60
    on_chat: Callable | None = None
    join_delay: float = 1.5
    respond_tick_sync: bool = True
    auto_resource_packs: bool = True
    chunk_radius: int = 8

    def resolve_player_uuid(self) -> str:
        if self.player_uuid:
            return self.player_uuid
        self.player_uuid = str(uuid.uuid4())
        return self.player_uuid

    def resolve_device_id(self) -> str:
        if self.device_id:
            return self.device_id
        self.device_id = str(uuid.uuid4())
        return self.device_id

    def resolve_client_random_id(self) -> int:
        if self.client_random_id is not None:
            return self.client_random_id
        import random
        self.client_random_id = random.getrandbits(63)
        return self.client_random_id
