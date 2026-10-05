# tools/supervision.py
import logging
from asterisk import ari
from security.auth import require_roles
from security.context import current_user

logger = logging.getLogger(__name__)


def _audit(tool: str, args: dict, result: str):
    u = current_user()
    logger.info(f"AUDIT user={u.username if u else '?'} tool={tool} args={args} result={str(result)[:200]}")


def register_supervision_tools(mcp):

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def get_asterisk_info() -> dict:
        """Récupère les informations système générales du serveur Asterisk."""
        data = ari.get("/asterisk/info")
        _audit("get_asterisk_info", {}, data)
        return data or {"error": "Impossible de récupérer les infos Asterisk"}

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def list_active_channels() -> list:
        """Liste tous les canaux/appels actuellement actifs sur Asterisk."""
        channels = ari.get("/channels") or []
        result = [
            {
                "id": ch.get("id"),
                "name": ch.get("name"),
                "state": ch.get("state"),
                "caller": ch.get("caller", {}).get("number"),
                "connected": ch.get("connected", {}).get("number"),
                "duration": ch.get("duration"),
            }
            for ch in channels
        ]
        _audit("list_active_channels", {}, f"{len(result)} canaux")
        return result

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def get_channel_info(channel_id: str) -> dict:
        """Récupère les détails d'un canal spécifique par son ID."""
        data = ari.get(f"/channels/{channel_id}")
        _audit("get_channel_info", {"channel_id": channel_id}, data)
        return data or {"error": f"Canal {channel_id} introuvable"}

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def list_endpoints() -> list:
        """Liste tous les comptes SIP / PJSIP configurés sur le serveur."""
        endpoints = ari.get("/endpoints") or []
        result = [
            {
                "technology": ep.get("technology"),
                "resource": ep.get("resource"),
                "state": ep.get("state"),
                "channel_ids": ep.get("channel_ids", []),
            }
            for ep in endpoints
        ]
        _audit("list_endpoints", {}, f"{len(result)} endpoints")
        return result

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def get_extension_status(extension: str) -> dict:
        """Récupère l'état d'une extension PJSIP (ex: 1001)."""
        data = ari.get(f"/endpoints/PJSIP/{extension}")
        _audit("get_extension_status", {"extension": extension}, data)
        return data or {"error": f"Extension {extension} introuvable"}

    @mcp.tool()
    @require_roles(["admin", "supervisor", "operator"])
    def get_queue_stats() -> dict:
        """Récupère l'état et les statistiques des files d'attente."""
        queues = ari.get("/queues") or []
        result = []
        for q in queues:
            name = q.get("name")
            detail = ari.get(f"/queues/{name}") or {}
            result.append({
                "name": name,
                "strategy": detail.get("strategy"),
                "callers_waiting": len(detail.get("callers", [])),
                "members": len(detail.get("members", [])),
                "max_length": q.get("max"),
                "average_wait_time": q.get("averageWaitTime"),
                "completed_calls": q.get("completed"),
                "abandoned_calls": q.get("abandoned"),
            })
        _audit("get_queue_stats", {}, f"{len(result)} queues")
        return {"total_queues": len(result), "queues": result}
