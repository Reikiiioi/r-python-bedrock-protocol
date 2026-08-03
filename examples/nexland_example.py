"""
Nexland.fun bot — full-featured example
Connects on 1.20.80, stays forever, collects chat, sends !привет! on join.

Usage:
    python examples/nexland_bot.py
    python examples/nexland_bot.py --username MyName --device windows --log-level DEBUG
"""

import asyncio
import argparse
import logging
import signal

from r_python_bedrock_protocol import Bot, BotConfig
from r_python_bedrock_protocol.config import SkinConfig
from r_python_bedrock_protocol.protocol.devices import list_presets


# ─────────────────────────── CLI args ─────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Nexland.fun Bedrock bot (forever-running, chat collector)"
    )
    p.add_argument("--host",        default="nexland.fun",  help="Server hostname")
    p.add_argument("--port",        default=19136,          type=int)
    p.add_argument("--username",    default="PythonBot",    help="In-game name")
    p.add_argument("--version",     default="1.20.80",      help="Game version, e.g. 1.20.80")
    p.add_argument(
        "--device", default="android",
        choices=list_presets(),
        help="Device preset to spoof",
    )
    p.add_argument("--device-model", default=None,          help="Override device model string")
    p.add_argument("--device-id",    default=None,          help="Override device UUID")
    p.add_argument("--language",    default="en_US",         help="Language code, e.g. ru_RU")
    p.add_argument("--log-level",   default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file",    default=None,           help="Write logs to this file")
    p.add_argument("--chat-log",    default="chat.log",     help="Write chat to this file")
    p.add_argument("--chat-json",   default="chat.json",    help="Autosave chat history JSON")
    p.add_argument("--autosave",    default=60,             type=int,
                   help="Chat autosave interval in seconds")
    p.add_argument("--no-reconnect", action="store_true",   help="Disable auto-reconnect")
    p.add_argument("--reconnect-delay", default=5.0,        type=float)
    p.add_argument("--max-reconnects",  default=-1,         type=int,
                   help="Max reconnect attempts (-1 = unlimited)")
    p.add_argument("--timeout",     default=12.0,           type=float,
                   help="Connection timeout in seconds")
    p.add_argument("--join-delay",  default=1.5,            type=float,
                   help="Seconds to wait after join before sending messages")
    p.add_argument("--message",     default="!привет!",     help="Message to send on join")
    p.add_argument("--chunk-radius", default=8,             type=int)
    p.add_argument("--log-packets", action="store_true",    help="Log every incoming packet ID")
    return p.parse_args()


# ─────────────────────────── Main ─────────────────────────────────────

async def main():
    args = parse_args()

    # Build full config
    config = BotConfig(
        username=args.username,
        language_code=args.language,

        # Device spoofing
        device=args.device,
        device_model=args.device_model,
        device_id=args.device_id,

        # Connection
        version=args.version,
        offline=True,
        connect_timeout=args.timeout,

        # Reconnect
        auto_reconnect=not args.no_reconnect,
        reconnect_delay=args.reconnect_delay,
        reconnect_delay_max=120.0,
        max_reconnects=args.max_reconnects,

        # Logging
        log_level=args.log_level,
        log_file=args.log_file,
        log_format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        chat_log_file=args.chat_log,
        log_packets=args.log_packets,

        # Chat / data collection
        chat_history_size=5000,
        chat_autosave_file=args.chat_json,
        chat_autosave_interval=args.autosave,

        # Behaviour
        join_delay=args.join_delay,
        chunk_radius=args.chunk_radius,
        auto_resource_packs=True,
        respond_tick_sync=True,
    )

    bot = Bot(args.host, args.port, config=config)

    # ── Event handlers ──────────────────────────────────────────────

    @bot.on("connect")
    def on_connect():
        print(f"[+] Connected to {args.host}:{args.port}")

    @bot.on("spawn")
    def on_spawn():
        print("[*] Login accepted — loading world…")

    @bot.on("start_game")
    def on_start_game(data):
        x, y, z = data.get("spawn", (0, 0, 0))
        gm = data.get("player_gamemode", "?")
        print(f"[*] StartGame  gamemode={gm}  spawn=({x:.1f}, {y:.1f}, {z:.1f})")

    @bot.on("join")
    async def on_join():
        print(f"[+] Joined!  Sending: {args.message!r}")
        await bot.send_message(args.message, delay=args.join_delay)
        print(f"[*] Uptime: {bot.stats.uptime:.1f}s  "
              f"Session: {bot.stats.session_time:.1f}s")

    @bot.on("chat")
    def on_chat(entry: dict):
        ts  = entry["ts"]
        src = entry.get("source", "")
        msg = entry["message"]
        label = f"<{src}>" if src else "[server]"
        print(f"  {label} {msg}")

    @bot.on("disconnect")
    def on_disconnect(reason: str):
        print(f"[-] Disconnected: {reason or '(server closed)'}")
        print(f"    Messages collected: {bot.stats.messages_received}")

    @bot.on("reconnecting")
    def on_reconnecting(info: dict):
        print(f"[~] Reconnecting in {info['delay']:.1f}s (attempt #{info['attempt']})…")

    @bot.on("error")
    def on_error(exc: Exception):
        print(f"[!] Error: {exc}")

    @bot.on("stopped")
    def on_stopped():
        # Final save
        if bot.chat_history:
            bot.save_chat(args.chat_json)
        stats = bot.stats.to_dict()
        print(f"\n[✓] Bot stopped. Stats: {stats}")

    # ── Ctrl-C / SIGTERM graceful shutdown ───────────────────────────

    loop = asyncio.get_running_loop()

    def _shutdown():
        print("\n[!] Shutting down…")
        asyncio.ensure_future(bot.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows: SIGTERM not supported, KeyboardInterrupt handles it

    print(f"""
╔══════════════════════════════════════╗
║  r-python-bedrock-protocol  Bot      ║
╠══════════════════════════════════════╣
║  Host     : {args.host}:{args.port:<20}║
║  Version  : {args.version:<27}║
║  Username : {args.username:<27}║
║  Device   : {args.device:<27}║
║  Reconnect: {'off' if args.no_reconnect else 'on':<27}║
║  Chat log : {args.chat_log:<27}║
╚══════════════════════════════════════╝
""")

    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
