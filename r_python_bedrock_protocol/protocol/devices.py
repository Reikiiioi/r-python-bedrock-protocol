from enum import IntEnum
from dataclasses import dataclass, field
import uuid as _uuid

class DeviceOS(IntEnum):
    UNKNOWN = 0
    ANDROID = 1
    IOS = 2
    MACOS = 3
    FIRE_OS = 4
    GEAR_VR = 5
    HOLOLENS = 6
    WINDOWS_10 = 7
    WIN32 = 8
    EDUCATION = 9
    WINDOWS_PHONE = 10
    XBOX = 11
    PS4 = 12
    NINTENDO_SWITCH = 13
    XBOX_ONE = 14
    WINDOWS_MOBILE = 15
    DEDICATED = 16

class InputMode(IntEnum):
    UNKNOWN = 0
    MOUSE = 1
    TOUCH = 2
    GAMEPAD = 3
    MOTION_CONTROLLER = 4

class UIProfile(IntEnum):
    CLASSIC = 0
    POCKET = 1

@dataclass(frozen=True)
class DevicePreset:
    name: str
    os: DeviceOS
    model: str
    input_mode: InputMode
    ui_profile: UIProfile
    platform_online_id: str = ''
DEVICE_PRESETS: dict[str, DevicePreset] = {'android': DevicePreset(name='android', os=DeviceOS.ANDROID, model='Samsung Galaxy S21 Ultra', input_mode=InputMode.TOUCH, ui_profile=UIProfile.POCKET), 'android_budget': DevicePreset(name='android_budget', os=DeviceOS.ANDROID, model='Redmi Note 10', input_mode=InputMode.TOUCH, ui_profile=UIProfile.POCKET), 'ios': DevicePreset(name='ios', os=DeviceOS.IOS, model='iPhone 14 Pro', input_mode=InputMode.TOUCH, ui_profile=UIProfile.POCKET), 'ipad': DevicePreset(name='ipad', os=DeviceOS.IOS, model='iPad Pro (12.9-inch)', input_mode=InputMode.TOUCH, ui_profile=UIProfile.CLASSIC), 'windows': DevicePreset(name='windows', os=DeviceOS.WINDOWS_10, model='Windows 10', input_mode=InputMode.MOUSE, ui_profile=UIProfile.CLASSIC), 'windows_laptop': DevicePreset(name='windows_laptop', os=DeviceOS.WINDOWS_10, model='Surface Laptop 5', input_mode=InputMode.MOUSE, ui_profile=UIProfile.CLASSIC), 'xbox': DevicePreset(name='xbox', os=DeviceOS.XBOX, model='Xbox Series X', input_mode=InputMode.GAMEPAD, ui_profile=UIProfile.CLASSIC), 'xbox_one': DevicePreset(name='xbox_one', os=DeviceOS.XBOX_ONE, model='Xbox One S', input_mode=InputMode.GAMEPAD, ui_profile=UIProfile.CLASSIC), 'switch': DevicePreset(name='switch', os=DeviceOS.NINTENDO_SWITCH, model='Nintendo Switch OLED', input_mode=InputMode.GAMEPAD, ui_profile=UIProfile.CLASSIC), 'ps4': DevicePreset(name='ps4', os=DeviceOS.PS4, model='PlayStation 4 Pro', input_mode=InputMode.GAMEPAD, ui_profile=UIProfile.CLASSIC), 'amazon': DevicePreset(name='amazon', os=DeviceOS.FIRE_OS, model='Amazon Fire HD 10', input_mode=InputMode.TOUCH, ui_profile=UIProfile.POCKET), 'dedicated': DevicePreset(name='dedicated', os=DeviceOS.DEDICATED, model='Dedicated Server', input_mode=InputMode.UNKNOWN, ui_profile=UIProfile.CLASSIC)}
DEFAULT_DEVICE = 'android'

def get_preset(name: str) -> DevicePreset:
    try:
        return DEVICE_PRESETS[name.lower()]
    except KeyError:
        known = ', '.join(sorted(DEVICE_PRESETS))
        raise ValueError(f'Unknown device preset {name!r}. Available: {known}') from None

def list_presets() -> list[str]:
    return sorted(DEVICE_PRESETS)
