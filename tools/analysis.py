# tools/analysis.py
import logging
from asterisk import ari, cdr
from security.auth import require_roles
from security.context import current_user

logger = logging.getLogger(__name__)


def _audit(tool: str, args: dict, result: str):
    u = current_user()
    logger.info(f"AUDIT user={u.username if u else '?'} tool={tool} args={args} result={str(result)[:200]}")


def register_analysis_tools(mcp):

    @mcp.tool()
    @require_roles(["admin", "supervisor"])
    def get_cdr_report(start_date: str = "", end_date: str = "", limit: int = 50) -> dict:
        """
        Historique des appels (CDR). Dates au format 'YYYY-MM-DD HH:MM:SS'.
        Si vides, retourne les derniers appels.
        """
        if start_date and end_date:
            sql = """
                SELECT calldate, clid, src, dst, dcontext, channel, dstchannel,
                       lastapp, lastdata, duration, billsec, disposition, uniqueid
                FROM cdr
                WHERE calldate BETWEEN %s AND %s
                ORDER BY calldate DESC LIMIT %s
            """
            rows = cdr.query(sql, (start_date, end_date, limit))
        else:
            sql = """
                SELECT calldate, clid, src, dst, dcontext, channel, dstchannel,
                       lastapp, lastdata, duration, billsec, disposition, uniqueid
                FROM cdr
                ORDER BY calldate DESC LIMIT %s
            """
            rows = cdr.query(sql, (limit,))

        # Conversion datetime → str pour JSON
        for r in rows:
            if "calldate" in r and r["calldate"]:
                r["calldate"] = str(r["calldate"])

        _audit("get_cdr_report", {"start": start_date, "end": end_date, "limit": limit}, f"{len(rows)} appels")
        return {"total": len(rows), "calls": rows}

    @mcp.tool()
    @require_roles(["admin", "supervisor"])
    def analyze_call_quality(channel_id: str) -> dict:
        """
        Analyse la qualité RTP d'un canal (jitter, packet loss, MOS via E-model simplifié).
        """
        stats = ari.get(f"/channels/{channel_id}/rtp_statistics")
        if not stats:
            return {"error": f"Pas de stats RTP pour {channel_id}"}

        rtp = stats.get("rtp", {})
        jitter = float(rtp.get("jitter", 0))
        packet_loss = float(rtp.get("packet_loss", 0))
        rtt = float(rtp.get("rtt", 0))

        # E-model simplifié (ITU-T G.107)
        delay_impairment = 0.024 * rtt
        if rtt > 177.3:
            delay_impairment += 0.11 * (rtt - 177.3)
        equipment_impairment = 30 * (packet_loss / 100.0)
        jitter_impairment = jitter * 0.5

        r_factor = max(0, min(100, 93.2 - delay_impairment - equipment_impairment - jitter_impairment))

        if r_factor > 100:
            mos = 4.5
        elif r_factor < 0:
            mos = 1.0
        else:
            mos = 1 + 0.035 * r_factor + 7e-6 * r_factor * (r_factor - 60) * (100 - r_factor)

        quality = (
            "Excellente" if mos >= 4.3 else
            "Bonne" if mos >= 4.0 else
            "Acceptable" if mos >= 3.6 else
            "Médiocre" if mos >= 3.1 else "Mauvaise"
        )

        result = {
            "channel_id": channel_id,
            "mos_score": round(mos, 2),
            "r_factor": round(r_factor, 2),
            "jitter_ms": jitter,
            "packet_loss_pct": packet_loss,
            "rtt_ms": rtt,
            "quality": quality,
        }
        _audit("analyze_call_quality", {"channel_id": channel_id}, result)
        return result

    @mcp.tool()
    @require_roles(["admin", "supervisor"])
    def get_trunk_utilization() -> dict:
        """Charge et utilisation des trunks PJSIP."""
        endpoints = ari.get("/endpoints") or []
        trunks = []
        total = 0
        for ep in endpoints:
            if ep.get("technology") == "PJSIP":
                chans = ep.get("channel_ids", [])
                trunks.append({
                    "name": ep.get("resource"),
                    "state": ep.get("state"),
                    "active_channels": len(chans),
                    "channel_ids": chans,
                })
                total += len(chans)
        result = {"total_trunks": len(trunks), "total_active_channels": total, "trunks": trunks}
        _audit("get_trunk_utilization", {}, result)
        return result
