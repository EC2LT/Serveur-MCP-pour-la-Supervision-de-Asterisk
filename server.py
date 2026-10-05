# server.py
import os
import logging
from fastmcp import FastMCP

from config.logging_config import setup_logging
from security.auth import authenticate_with_token
from security.context import get_current_token
from tools import register_all_tools

# --- Initialisation ---
setup_logging()
logger = logging.getLogger(__name__)

mcp = FastMCP("Asterisk-Supervisor-MCP")


# --- Authentification au démarrage ---
def _init_auth():
    """Récupère le token depuis l'environnement (transmis par l'agent)."""
    token = os.getenv("MCP_AUTH_TOKEN")
    if token:
        try:
            user = authenticate_with_token(token)
            logger.info(f"Authentifié : {user.username} (rôles: {user.roles})")
        except Exception as e:
            logger.error(f"Échec authentification : {e}")
    else:
        logger.warning("Aucun token fourni. Les outils protégés échoueront.")


_init_auth()

# --- Enregistrement des outils ---
register_all_tools(mcp)


if __name__ == "__main__":
    logger.info("Démarrage du serveur MCP Asterisk...")
    mcp.run(transport="stdio")
