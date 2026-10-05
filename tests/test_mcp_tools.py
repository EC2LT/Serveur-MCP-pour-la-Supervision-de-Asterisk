# tests/test_mcp_tools.py
"""Tests basiques des outils MCP (sans authentification, en dev)."""
import os
os.environ["MCP_ROLE"] = "admin"

from asterisk import ari


def test_ari_connection():
    """Vérifie que l'ARI est joignable."""
    info = ari.get("/asterisk/info")
    assert info is not None, "ARI inaccessible"
    print(f"✅ ARI OK : {info.get('system', {}).get('version', '?')}")


def test_list_channels():
    """Vérifie la récupération des canaux."""
    channels = ari.get("/channels")
    assert channels is not None
    print(f"✅ {len(channels)} canaux actifs")


def test_list_endpoints():
    """Vérifie la récupération des endpoints."""
    endpoints = ari.get("/endpoints")
    assert endpoints is not None
    print(f"✅ {len(endpoints)} endpoints configurés")


if __name__ == "__main__":
    test_ari_connection()
    test_list_channels()
    test_list_endpoints()
