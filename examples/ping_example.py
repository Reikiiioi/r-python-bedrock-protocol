"""Example pinging Bedrock server status."""

import asyncio
from r_python_bedrock_protocol import ping


async def main():
    print("Pinging Bedrock server...")
    info = await ping("play.cubecraft.net", 19132)
    print(f"MOTD: {info.motd}")
    print(f"Version: {info.version} (Protocol {info.protocol_version})")
    print(f"Players: {info.players_online}/{info.players_max}")


if __name__ == "__main__":
    asyncio.run(main())
