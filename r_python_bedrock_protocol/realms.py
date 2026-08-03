import httpx
from typing import Any
_REALMS_BASE = 'https://pocket.realms.minecraft.net'
_REALMS_HEADERS = {'User-Agent': 'MCPE/Android', 'Client-Version': '1.21.0'}

class RealmsAPI:

    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self._http = httpx.AsyncClient(base_url=_REALMS_BASE, headers={**_REALMS_HEADERS, 'Authorization': f'Bearer {auth_token}'}, timeout=15.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        await self._http.aclose()

    async def get_realms(self) -> list[dict[str, Any]]:
        resp = await self._http.get('/worlds')
        resp.raise_for_status()
        return resp.json().get('servers', [])

    async def get_realm_address(self, realm_id: int) -> tuple[str, int]:
        resp = await self._http.get(f'/worlds/{realm_id}/join')
        resp.raise_for_status()
        data = resp.json()
        address = data.get('address', '')
        if ':' in address:
            host, port_str = address.split(':', 1)
            return (host, int(port_str))
        return (address, 19132)
