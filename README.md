# r-python-bedrock-protocol

Высокопроизводительная асинхронная библиотека на Python для работы с сетевым протоколом **Minecraft: Bedrock Edition** (MCPE).

**Автор:** [Reikiioi](https://github.com/Reikiioi)  
**Вдохновлено:** [bedrock-protocol](https://github.com/PrismarineJS/bedrock-protocol) от команды PrismarineJS.

---

## ⚡ Особенности

- **Асинхронность и скорость**: Построено на `asyncio` и поддерживается `uvloop` для минимальных задержек и высокой пропускной способности I/O.
- **Быстрая криптография**: Прямая интеграция OpenSSL (`cryptography`) для шифрования пакетов AES-256-CFB8 и ECDH ключей.
- **Простой и удобный API**: Простая событийная модель (`@client.on('text')`, `@server.on('connect')`).
- **Транспорт RakNet**: Асинхронный клиент и сервер протокола RakNet UDP.
- **Встроенный Пинг**: Получение статуса сервера (MOTD, количество игроков, версия протокола).
- **MITM Прокси (Relay)**: Удобный инструмент для анализа и перехвата пакетов.

---

## 🚀 Установка

```bash
pip install r-python-bedrock-protocol
```

Или из исходного кода:

```bash
git clone https://github.com/Reikiioi/r-python-bedrock-protocol.git
cd r-python-bedrock-protocol
pip install -e .
```

---

## 💻 Примеры использования

### 1. Подключение Клиента (Echo-бот)

```python
import asyncio
from r_python_bedrock_protocol import create_client

async def main():
    client = create_client(
        host="127.0.0.1",
        port=19132,
        username="Steve",
        offline=True
    )

    @client.on("connect")
    def on_connect():
        print("Подключено к серверу!")

    @client.on("join")
    def on_join():
        print("Успешный вход в мир!")

    @client.on("text")
    def on_text(packet):
        print(f"{packet.get('source_name')}: {packet.get('message')}")

    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 2. Запрос статуса сервера (Ping)

```python
import asyncio
from r_python_bedrock_protocol import ping

async def main():
    info = await ping("play.cubecraft.net", 19132)
    print(f"Сервер: {info.motd}")
    print(f"Версия: {info.version} (Протокол {info.protocol_version})")
    print(f"Игроки: {info.players_online}/{info.players_max}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 3. Запуск Сервера

```python
import asyncio
from r_python_bedrock_protocol import create_server

async def main():
    server = create_server(host="0.0.0.0", port=19132, motd="Мой Bedrock Сервер")

    @server.on("connect")
    def on_connect(client):
        print(f"Новое подключение: {client.address}")

    await server.listen()
    print("Сервер запущен на 0.0.0.0:19132")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📜 Лицензия

Распространяется под лицензией [MIT](LICENSE).  
Copyright (c) 2026 **Reikiioi**.
