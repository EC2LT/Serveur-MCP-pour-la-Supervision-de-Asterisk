# asterisk/ari_client.py
import logging
import aiohttp
import requests
from config import settings

logger = logging.getLogger(__name__)


class ARIClient:
    """Client ARI synchrone (pour les outils MCP) et async (pour le S2S)."""

    def __init__(self):
        self.url = settings.ARI_URL
        self.auth = settings.ari_auth

    # --- Méthodes synchrones (utilisées par les outils MCP) ---
    def get(self, path: str, params: dict = None) -> dict | list | None:
        try:
            r = requests.get(f"{self.url}{path}", auth=self.auth, params=params, timeout=5)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"ARI GET {path} → {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"ARI GET {path} erreur : {e}")
            return None

    def post(self, path: str, params: dict = None, json: dict = None) -> dict | None:
        try:
            r = requests.post(f"{self.url}{path}", auth=self.auth, params=params, json=json, timeout=10)
            if r.status_code in (200, 201):
                try:
                    return r.json()
                except Exception:
                    return {}
            logger.warning(f"ARI POST {path} → {r.status_code} : {r.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"ARI POST {path} erreur : {e}")
            return None

    def delete(self, path: str, params: dict = None) -> bool:
        try:
            r = requests.delete(f"{self.url}{path}", auth=self.auth, params=params, timeout=5)
            return r.status_code in (200, 204)
        except Exception as e:
            logger.error(f"ARI DELETE {path} erreur : {e}")
            return False

    # --- Méthodes async (utilisées par vocal_agent) ---
    async def apost(self, session: aiohttp.ClientSession, path: str, params: dict = None) -> dict:
        async with session.post(f"{self.url}{path}", params=params) as resp:
            try:
                return await resp.json()
            except Exception:
                return {}

    async def adelete(self, session: aiohttp.ClientSession, path: str) -> bool:
        async with session.delete(f"{self.url}{path}") as resp:
            return resp.status in (200, 204)


ari = ARIClient()
