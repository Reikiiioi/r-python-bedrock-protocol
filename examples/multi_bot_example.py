import asyncio
from r_python_bedrock_protocol import BotCluster, BotConfig

async def main():
    config_template = BotConfig(
        version="1.20.80",
        device="windows",
        auto_reconnect=True,
        reconnect_delay=3.0,
    )
    cluster = BotCluster.create_swarm(
        host="127.0.0.1",
        port=19132,
        names=["Worker_Alpha", "Worker_Beta", "Worker_Gamma"],
        config_template=config_template
    )

    def setup_bot(bot):
        @bot.on("connect")
        def on_connect():
            print(f"[{bot.config.username}] Connected!")

        @bot.on("join")
        async def on_join():
            print(f"[{bot.config.username}] Joined world!")
            await bot.send_message(f"Hello from {bot.config.username}!")

        @bot.on("chat")
        def on_chat(entry):
            print(f"[{bot.config.username}] Chat <{entry.get('source')}>: {entry.get('message')}")

    for bot in cluster.bots:
        setup_bot(bot)

    print("Launching cluster of 3 bots...")
    await cluster.run_all()

if __name__ == "__main__":
    asyncio.run(main())
