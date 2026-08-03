"""Example Bedrock Client echo bot."""

import asyncio
from r_python_bedrock_protocol import create_client


async def main():
    # Create simple client instance
    client = create_client(
        host="127.0.0.1",
        port=19132,
        username="ReikiioiBot",
        offline=True
    )

    @client.on("connect")
    def on_connect():
        print("Successfully connected to Bedrock server!")

    @client.on("join")
    def on_join():
        print("Joined world!")

    @client.on("text")
    def on_text(packet):
        print(f"Chat: {packet.get('source_name')}: {packet.get('message')}")
        # Echo message back
        client.send("text", {"message": f"Echo: {packet.get('message')}"})

    await client.connect()


if __name__ == "__main__":
    asyncio.run(main())
