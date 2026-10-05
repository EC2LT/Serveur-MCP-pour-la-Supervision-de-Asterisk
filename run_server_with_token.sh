#!/bin/bash
# run_server_with_token.sh
# Récupère un token Keycloak et lance le serveur MCP avec ce token

set -e

USERNAME="${1:-alice}"
PASSWORD="${2:-password}"

echo "🔐 Récupération du token pour $USERNAME..."

TOKEN=$(curl -s -X POST http://localhost:8090/realms/mcp-asterisk/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=mcp-agent" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Échec de récupération du token pour $USERNAME"
    exit 1
fi

echo "✅ Token récupéré (${TOKEN:0:30}...)"
echo "🚀 Lancement du serveur MCP..."

export MCP_AUTH_TOKEN="$TOKEN"
exec python3 server.py
