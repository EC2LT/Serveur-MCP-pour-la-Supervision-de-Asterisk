# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Asterisk ARI
    ARI_URL = os.getenv("ARI_URL", "http://localhost:8088/ari")
    ARI_WS_URL = os.getenv("ARI_WS_URL", "ws://localhost:8088/ari/events")
    ARI_USER = os.getenv("ARI_USER", "mcp_user")
    ARI_PASSWORD = os.getenv("ARI_PASSWORD", "mcp_secret_password")
    ARI_APP = os.getenv("ARI_APP", "asterisk-vocal-ai")

    # AMI
    AMI_HOST = os.getenv("AMI_HOST", "127.0.0.1")
    AMI_PORT = int(os.getenv("AMI_PORT", "5038"))
    AMI_USER = os.getenv("AMI_USER", "mcp_ami_user")
    AMI_PASSWORD = os.getenv("AMI_PASSWORD", "ami_secret_password")

    # CDR
    CDR_DB_HOST = os.getenv("CDR_DB_HOST", "localhost")
    CDR_DB_USER = os.getenv("CDR_DB_USER", "asterisk")
    CDR_DB_PASSWORD = os.getenv("CDR_DB_PASSWORD", "asterisk")
    CDR_DB_NAME = os.getenv("CDR_DB_NAME", "asterisk")

    # Keycloak
    KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8090")
    KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mcp-asterisk")
    KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "mcp-agent")

    # Ollama
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    # S2S
    UDP_IP = os.getenv("UDP_IP", "127.0.0.1")
    UDP_PORT = int(os.getenv("UDP_PORT", "5088"))
    PIPER_MODEL = os.getenv("PIPER_MODEL", "./models/fr_FR-siwis-medium.onnx")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

    # Dev
    MCP_ROLE = os.getenv("MCP_ROLE", "admin")

    @property
    def ari_auth(self):
        return (self.ARI_USER, self.ARI_PASSWORD)


settings = Settings()
