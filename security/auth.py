# security/auth.py
import time
import logging
import requests
from functools import wraps
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError

from config import settings
from security.context import set_current_token, set_current_user, UserContext, get_current_token

logger = logging.getLogger("auth")

ISSUER = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
TOKEN_URL = f"{ISSUER}/protocol/openid-connect/token"

_jwks_cache = {"keys": None, "expires_at": 0}
JWKS_TTL = 3600


def get_jwks():
    """Récupère les clés publiques Keycloak (avec cache 1h)."""
    now = time.time()
    if _jwks_cache["keys"] is None or now > _jwks_cache["expires_at"]:
        resp = requests.get(JWKS_URL, timeout=5)
        resp.raise_for_status()
        _jwks_cache["keys"] = resp.json()
        _jwks_cache["expires_at"] = now + JWKS_TTL
        logger.info("JWKS rechargées.")
    return _jwks_cache["keys"]


def verify_token(token: str) -> dict:
    """Vérifie un JWT Keycloak. Retourne le payload."""
    try:
        jwks = get_jwks()
        return jwt.decode(
            token, jwks, algorithms=["RS256"],
            audience="account", issuer=ISSUER,
        )
    except ExpiredSignatureError:
        raise ValueError("Token expiré.")
    except JWTError as e:
        raise ValueError(f"Token invalide : {e}")


def extract_roles(payload: dict) -> list[str]:
    return payload.get("realm_access", {}).get("roles", [])


def has_role(payload: dict, required: list[str]) -> bool:
    return bool(set(extract_roles(payload)) & set(required))


def login(username: str, password: str) -> dict:
    """Authentification Keycloak (Resource Owner Password, dev only)."""
    data = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "username": username,
        "password": password,
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Échec login : {resp.text}")
    return resp.json()


def authenticate_with_token(token: str) -> UserContext:
    """Vérifie un token et construit le contexte utilisateur."""
    payload = verify_token(token)
    user = UserContext(
        username=payload.get("preferred_username", "unknown"),
        roles=extract_roles(payload),
        token=token,
    )
    set_current_token(token)
    set_current_user(user)
    return user


def require_roles(required: list[str]):
    """Décorateur de protection par rôles."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = get_current_token()
            if not token:
                raise PermissionError("Token manquant. Authentification requise.")
            payload = verify_token(token)
            if not has_role(payload, required):
                raise PermissionError(
                    f"Rôle requis : {required}. "
                    f"Rôles actuels : {extract_roles(payload)}"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def refresh_token(refresh_token_str: str) -> dict:
    """Rafraîchit un access token expiré."""
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "refresh_token": refresh_token_str,
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Échec refresh token : {resp.text}")
    return resp.json()
