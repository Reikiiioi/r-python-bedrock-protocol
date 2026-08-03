import httpx
from typing import Any

class XboxAuthError(Exception):
    pass

class XboxAuthHandler:

    def __init__(self, client_id: str='0000000044124CBE'):
        self.client_id = client_id
        self.user_token: str | None = None
        self.xsts_token: str | None = None
        self.xuid: str | None = None

    async def authenticate_xbox_live(self, ms_access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as http:
            user_resp = await http.post('https://user.auth.xboxlive.com/user/authenticate', json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com', 'RpsTicket': f'd={ms_access_token}'}, 'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'})
            if user_resp.status_code != 200:
                raise XboxAuthError(f'Xbox Live user auth failed: HTTP {user_resp.status_code} — {user_resp.text[:200]}')
            user_data = user_resp.json()
            if 'Token' not in user_data:
                raise XboxAuthError(f'Xbox Live user auth: missing Token in response: {user_data}')
            user_token = user_data['Token']
            xsts_resp = await http.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [user_token]}, 'RelyingParty': 'https://multiplayer.minecraft.net/', 'TokenType': 'JWT'})
            if xsts_resp.status_code != 200:
                raise XboxAuthError(f'XSTS auth failed: HTTP {xsts_resp.status_code} — {xsts_resp.text[:200]}')
            xsts_data = xsts_resp.json()
            if 'Token' not in xsts_data:
                raise XboxAuthError(f'XSTS auth: missing Token in response: {xsts_data}')
            xui = xsts_data.get('DisplayClaims', {}).get('xui', [{}])[0]
            self.xsts_token = xsts_data['Token']
            self.xuid = xui.get('xid', '')
            return {'user_hash': xui.get('uhs', ''), 'xsts_token': self.xsts_token, 'xuid': self.xuid}
