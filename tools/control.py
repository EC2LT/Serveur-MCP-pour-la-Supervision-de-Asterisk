# tools/control.py
import logging
from asterisk import ari
from security.auth import require_roles
from security.context import current_user

logger = logging.getLogger(__name__)


def _audit(tool: str, args: dict, result: str):
    u = current_user()
    logger.info(f"AUDIT user={u.username if u else '?'} tool={tool} args={args} result={str(result)[:200]}")


def register_control_tools(mcp):

    @mcp.tool()
    @require_roles(["admin"])
    def originate_call(endpoint: str, extension: str, context: str = "default") -> dict:
        """
        Initie un appel depuis un endpoint SIP vers une extension.
        ⚠️ Action critique (validation humaine côté agent).
        """
        result = ari.post("/channels", params={
            "endpoint": f"PJSIP/{endpoint}",
            "extension": extension,
            "context": context,
            "priority": 1,
        })
        _audit("originate_call", {"endpoint": endpoint, "extension": extension}, result)
        return result or {"error": "Échec de l'initiation d'appel"}

    @mcp.tool()
    @require_roles(["admin"])
    def make_call(endpoint: str, extension: str, context: str = "default") -> dict:
        """
        Alias de originate_call : initie un appel depuis un endpoint SIP vers une extension.
        ⚠️ Action critique (validation humaine côté agent).
        """
        return originate_call(endpoint=endpoint, extension=extension, context=context)

    @mcp.tool()
    @require_roles(["admin"])
    def hangup_channel(channel_id: str) -> dict:
        """Raccroche un canal actif. ⚠️ Action critique."""
        ok = ari.delete(f"/channels/{channel_id}")
        result = {"status": "success", "channel_id": channel_id} if ok else {"error": "Échec"}
        _audit("hangup_channel", {"channel_id": channel_id}, result)
        return result

    @mcp.tool()
    @require_roles(["admin"])
    def redirect_call(channel_id: str, extension: str, context: str = "default") -> dict:
        """Redirige un appel vers une autre extension. ⚠️ Action critique."""
        result = ari.post(f"/channels/{channel_id}/redirect", params={
            "endpoint": f"PJSIP/{extension}",
            "context": context,
            "priority": 1,
        })
        out = {"status": "redirected", "channel_id": channel_id, "to": extension} if result is not None else {"error": "Échec"}
        _audit("redirect_call", {"channel_id": channel_id, "extension": extension}, out)
        return out

    @mcp.tool()
    @require_roles(["admin", "supervisor"])
    def spy_channel(channel_id: str, spy_type: str = "listen") -> dict:
        """
        Écoute discrète (Chanspy) via ARI Snoop.
        ⚠️ Action critique. ⚠️ Consentement légal obligatoire.
        """
        result = ari.post(f"/channels/{channel_id}/snoop", params={
            "app": "asterisk-vocal-ai",
            "spy": "in" if spy_type == "listen" else "both",
            "whisper": "none",
        })
        if result:
            out = {
                "status": "spy_initiated",
                "target": channel_id,
                "type": spy_type,
                "snoop_channel_id": result.get("id"),
                "warning": "Écoute soumise au consentement légal des parties.",
            }
        else:
            out = {"error": "Échec de l'activation du Snoop"}
        _audit("spy_channel", {"channel_id": channel_id, "spy_type": spy_type}, out)
        return out
