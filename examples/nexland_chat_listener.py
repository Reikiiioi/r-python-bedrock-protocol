import asyncio
from r_python_bedrock_protocol import Bot, BotConfig

async def main():
    cfg = BotConfig(
        username="vh24rr",
        version="1.21.100",
        connect_timeout=20.0,
        auto_reconnect=False,
        log_level="ERROR"
    )
    bot = Bot("nexland.fun", 19136, config=cfg)


    @bot.on("connect")
    def on_connect():
        print("[+] Connected to nexland.fun:19136")

    @bot.on("chat")
    def on_chat(entry: dict):
        src = entry.get("source", "")
        msg = entry.get("message", "")
        if src:
            print(f"<{src}> {msg}")
        else:
            print(f"{msg}")

    async def timer():
        await asyncio.sleep(60)
        print("\n[*] 1 minute elapsed. Stopping bot...")
        await bot.stop()

    asyncio.create_task(timer())
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
