import asyncio
import json
import os
import bcrypt
import socketio
from aiohttp import web
from bot_controller import BotController, SingleBotManager

root_dir = os.path.dirname(__file__)
config_path = os.path.join(root_dir, 'config.json')

def load_config() -> dict:
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "lang": "en",
        "panel": {
            "port": 3000,
            "passwordHash": "",
            "sessionSecret": "auth_ok"
        },
        "botDefaults": {
            "host": "localhost",
            "port": 19132,
            "version": "1.20.80",
            "baseUsername": "Bot",
            "count": 10,
            "threadCount": 1,
            "delayBetweenBotsSeconds": 1,
            "finalDelaySeconds": 30,
            "messages": ["Hello!"]
        }
    }

def save_config(cfg: dict):
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()

locales = {}
locales_dir = os.path.join(root_dir, 'locales')
for l_code in ['en', 'ru']:
    l_path = os.path.join(locales_dir, f'{l_code}.json')
    if os.path.exists(l_path):
        with open(l_path, 'r', encoding='utf-8') as f:
            locales[l_code] = json.load(f)

lang = config.get('lang', 'en')
t_locale = locales.get(lang, locales.get('en', {}))

sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

bot_ctrl = BotController(config)
single_bot = SingleBotManager()

auth_tokens = set()

async def handle_locale(request):
    return web.json_response(t_locale)

async def handle_login(request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    pwd = data.get("password", "")
    pwd_hash = config.get("panel", {}).get("passwordHash", "")

    if not pwd_hash:
        return web.json_response({"success": True, "token": "auth_ok"})

    if not pwd:
        return web.json_response({"success": False, "error": "Password required"})

    try:
        if bcrypt.checkpw(pwd.encode('utf-8'), pwd_hash.encode('utf-8')):
            return web.json_response({"success": True, "token": "auth_ok"})
    except Exception:
        pass

    return web.json_response({"success": False, "error": "Invalid password"})

async def handle_get_config(request):
    token = request.query.get('token', '')
    if token != 'auth_ok':
        return web.json_response({"success": False, "error": "Unauthorized"})
    return web.json_response({"success": True, "config": config.get("botDefaults", {})})

async def handle_post_config(request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    token = data.get('token', '')
    if token != 'auth_ok':
        return web.json_response({"success": False, "error": "Unauthorized"})

    new_cfg = data.get('config', {})
    config["botDefaults"].update(new_cfg)
    save_config(config)
    return web.json_response({"success": True})

async def handle_index(request):
    return web.FileResponse(os.path.join(root_dir, 'public', 'index.html'))

async def handle_dashboard(request):
    return web.FileResponse(os.path.join(root_dir, 'public', 'dashboard.html'))

app.router.add_get('/api/locale', handle_locale)
app.router.add_post('/api/login', handle_login)
app.router.add_get('/api/config', handle_get_config)
app.router.add_post('/api/config', handle_post_config)
app.router.add_get('/', handle_index)
app.router.add_get('/dashboard.html', handle_dashboard)

public_dir = os.path.join(root_dir, 'public')
app.router.add_static('/', public_dir, show_index=True)

@sio.event
async def connect(sid, environ):
    pass

@sio.event
async def auth(sid, data):
    token = data.get('token') if isinstance(data, dict) else None
    if token == 'auth_ok':
        auth_tokens.add(sid)
        await sio.emit('status', bot_ctrl.get_status(), to=sid)
        await sio.emit('logs', bot_ctrl.get_logs(100), to=sid)
        await sio.emit('manual_status', single_bot.get_status(), to=sid)
        await sio.emit('manual_messages', single_bot.get_messages(100), to=sid)
        return {"success": True}
    return {"success": False, "error": "Invalid token"}

@sio.event
async def start(sid, config_data):
    if sid not in auth_tokens:
        return
    res = bot_ctrl.start(config_data or config.get("botDefaults", {}))
    if "error" in res:
        await sio.emit('log', {"type": "error", "message": res["error"], "time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z")}, to=sid)

@sio.event
async def stop(sid):
    if sid not in auth_tokens:
        return
    bot_ctrl.stop()

@sio.event
async def getStatus(sid):
    if sid not in auth_tokens:
        return
    await sio.emit('status', bot_ctrl.get_status(), to=sid)

@sio.event
async def connect_bot(sid, options):
    if sid not in auth_tokens:
        return
    await single_bot.connect(options)

@sio.event
async def disconnect_bot(sid):
    if sid not in auth_tokens:
        return
    await single_bot.disconnect()

@sio.event
async def bot_command(sid, text):
    if sid not in auth_tokens:
        return
    await single_bot.send_message(text)

@sio.event
async def disconnect(sid):
    auth_tokens.discard(sid)

def _on_bot_update(status_data):
    asyncio.create_task(sio.emit('status', status_data))

def _on_bot_log(log_entry):
    asyncio.create_task(sio.emit('log', log_entry))

def _on_single_status(status_data):
    asyncio.create_task(sio.emit('manual_status', status_data))

def _on_single_msg(msg_entry):
    asyncio.create_task(sio.emit('manual_message', msg_entry))

bot_ctrl.on('update', _on_bot_update)
bot_ctrl.on('log', _on_bot_log)
single_bot.on('status', _on_single_status)
single_bot.on('message', _on_single_msg)

async def start_app():
    port = config.get("panel", {}).get("port", 3000)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', port)
    await site.start()
    print(f"MineDDoS / BotMCBE Control Panel (Python) running on http://127.0.0.1:{port}")
