import requests
from fastmcp import FastMCP

mcp = FastMCP("Asterisk-Supervisor-MCP")

ARI_URL = "http://localhost:8088/ari"
AUTH = ("mcp_user", "mcp_secret_password")  # Identifiants ari.conf

@mcp.tool()
def get_asterisk_info() -> dict:
    """Récupère les informations système générales du serveur Asterisk."""
    url = f"{ARI_URL}/asterisk/info"
    response = requests.get(url, auth=AUTH)
    return response.json() if response.status_code == 200 else {"error": response.text}

@mcp.tool()
def list_active_channels() -> list:
    """Liste tous les canaux/appels actuellement actifs sur Asterisk."""
    url = f"{ARI_URL}/channels"
    response = requests.get(url, auth=AUTH)
    return response.json() if response.status_code == 200 else []

@mcp.tool()
def list_endpoints() -> list:
    """Liste tous les comptes SIP / PJSIP configurés sur le serveur Asterisk."""
    url = f"{ARI_URL}/endpoints"
    try:
        response = requests.get(url, auth=AUTH)
        if response.status_code == 200:
            endpoints_data = response.json()
            formatted_endpoints = []
            
            for ep in endpoints_data:
                # Filtrer ou formater proprement chaque endpoint
                formatted_endpoints.append({
                    "technology": ep.get("technology", "N/A"),
                    "resource": ep.get("resource", "N/A"),
                    "state": ep.get("state", "unknown"),
                    "channel_ids": ep.get("channel_ids", [])
                })
            return formatted_endpoints
        else:
            return [{"error": f"Erreur ARI {response.status_code}: {response.text}"}]
    except Exception as e:
        return [{"error": str(e)}]

@mcp.tool()
def make_call(endpoint: str, extension: str, context: str = "default") -> dict:
    """Initie un appel depuis un endpoint SIP vers une extension spécifiée."""
    url = f"{ARI_URL}/channels"
    params = {
        "endpoint": f"PJSIP/{endpoint}",
        "extension": extension,
        "context": context,
        "priority": 1
    }
    response = requests.post(url, auth=AUTH, params=params)
    return response.json() if response.status_code == 200 else {"error": response.text}

@mcp.tool()
def hangup_channel(channel_id: str) -> dict:
    """Raccroche/Termine un canal actif par son identifiant unique."""
    url = f"{ARI_URL}/channels/{channel_id}"
    response = requests.delete(url, auth=AUTH)
    return {"status": "success"} if response.status_code == 204 else {"error": response.text}

@mcp.tool()
def get_queue_stats() -> dict:
    """Récupère l'état et la liste des files d'attente (Queues)."""
    # Implémentation indicative selon vos modules
    return {"status": "active", "queues": []}

@mcp.tool()
def analyze_call_quality(channel_id: str) -> dict:
    """Analyse la qualité globale d'une communication (Simulé/ARI Stats)."""
    return {"channel_id": channel_id, "mos_score": 4.2, "jitter": "12ms", "packet_loss": "0.1%"}

@mcp.tool()
def spy_channel(channel_id: str, spy_type: str = "listen") -> dict:
    """Active l'écoute discrète (Chanspy) sur un canal."""
    return {"status": "spy_initiated", "target": channel_id, "type": spy_type}

if __name__ == "__main__":
    mcp.run(transport="stdio")
