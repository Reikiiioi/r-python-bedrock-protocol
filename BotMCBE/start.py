import asyncio
import os
import sys
import webbrowser
from server import start_app, config

async def main():
    port = config.get("panel", {}).get("port", 3000)
    print("=" * 60)
    print(f"  MineDDoS / BotMCBE Control Panel (Python Edition)")
    print(f"  URL: http://127.0.0.1:{port}")
    print("=" * 60)

    await start_app()

    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down BotMCBE server...")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
