import time
import uuid
import random
import base64
import jwt
from dataclasses import dataclass
from .ecdh import BedrockCryptoContext

def _make_default_skin_rgba() -> bytes:
    img = bytearray(64 * 64 * 4)
    skin_tone = (239, 198, 148, 255)
    dark_blue = (62, 84, 170, 255)
    dark_grey = (80, 80, 80, 255)
    for y in range(64):
        for x in range(64):
            if y < 16:
                c = skin_tone
            elif y < 32:
                c = dark_blue
            else:
                c = dark_grey
            idx = (y * 64 + x) * 4
            img[idx:idx + 4] = c
    return bytes(img)
_DEFAULT_SKIN_B64: str | None = None

def _get_default_skin_b64() -> str:
    global _DEFAULT_SKIN_B64
    if _DEFAULT_SKIN_B64 is None:
        _DEFAULT_SKIN_B64 = base64.b64encode(_make_default_skin_rgba()).decode('ascii')
    return _DEFAULT_SKIN_B64
_DEFAULT_RESOURCE_PATCH = base64.b64encode(b'{"geometry":{"default":"geometry.humanoid.custom"}}').decode('ascii')

@dataclass
class DeviceInfo:
    device_model: str = 'Samsung Galaxy S21 Ultra'
    device_os: int = 1
    device_id: str = ''
    client_random_id: int = 0
    game_version: str = '1.21.0'
    language_code: str = 'en_US'
    input_mode: int = 2
    ui_profile: int = 1
    gui_scale: int = 0
    server_address: str = '127.0.0.1:19132'
    title_id: str = '896928775'

    def __post_init__(self):
        if not self.device_id:
            self.device_id = str(uuid.uuid4())
        if not self.client_random_id:
            self.client_random_id = random.getrandbits(63)

def create_client_chain_jwt(username: str, client_uuid: str | None=None, crypto_ctx: BedrockCryptoContext | None=None, xuid: str='', title_id: str='896928775') -> str:
    if crypto_ctx is None:
        crypto_ctx = BedrockCryptoContext()
    if client_uuid is None:
        client_uuid = str(uuid.uuid4())
    pub_key_b64 = crypto_ctx.export_public_key_b64()
    now = int(time.time())
    payload = {'exp': now + 3600, 'nbf': now - 10, 'identityPublicKey': pub_key_b64, 'extraData': {'displayName': username, 'identity': client_uuid, 'titleId': title_id, 'XUID': xuid}}
    return jwt.encode(payload, crypto_ctx.private_key, algorithm='ES384', headers={'alg': 'ES384', 'x5u': pub_key_b64})

def create_client_skin_jwt(username: str, client_uuid: str | None=None, crypto_ctx: BedrockCryptoContext | None=None, device_info: DeviceInfo | None=None, skin_data_b64: str | None=None, skin_id: str='Steve', skin_width: int=64, skin_height: int=64, arm_size: str='wide', cape_data: str='', cape_id: str='', cape_on_classic: bool=False, is_persona: bool=False, persona_pieces: list | None=None, resource_patch_b64: str | None=None) -> str:
    if crypto_ctx is None:
        crypto_ctx = BedrockCryptoContext()
    if client_uuid is None:
        client_uuid = str(uuid.uuid4())
    if device_info is None:
        device_info = DeviceInfo()
    if skin_data_b64 is None:
        skin_data_b64 = _get_default_skin_b64()
    if resource_patch_b64 is None:
        resource_patch_b64 = _DEFAULT_RESOURCE_PATCH
    if persona_pieces is None:
        persona_pieces = []
    pub_key_b64 = crypto_ctx.export_public_key_b64()
    payload = {'AnimatedImageData': [], 'ArmSize': arm_size, 'CapeData': cape_data, 'CapeId': cape_id, 'CapeImageHeight': 0, 'CapeImageWidth': 0, 'CapeOnClassicSkin': cape_on_classic, 'PersonaPieces': persona_pieces, 'PersonaSkin': is_persona, 'SkinData': skin_data_b64, 'SkinId': skin_id, 'SkinImageHeight': skin_height, 'SkinImageWidth': skin_width, 'SkinResourcePatch': resource_patch_b64, 'ClientRandomId': device_info.client_random_id, 'CurrentInputMode': device_info.input_mode, 'DefaultInputMode': device_info.input_mode, 'DeviceId': device_info.device_id, 'DeviceModel': device_info.device_model, 'DeviceOS': device_info.device_os, 'GameVersion': device_info.game_version, 'GuiScale': device_info.gui_scale, 'LanguageCode': device_info.language_code, 'UIProfile': device_info.ui_profile, 'SelfSignedId': client_uuid, 'ServerAddress': device_info.server_address, 'ThirdPartyName': username, 'ThirdPartyNameOnly': False, 'PlatformOfflineId': '', 'PlatformOnlineId': '', 'PlatformUserId': ''}
    return jwt.encode(payload, crypto_ctx.private_key, algorithm='ES384', headers={'alg': 'ES384', 'x5u': pub_key_b64})
