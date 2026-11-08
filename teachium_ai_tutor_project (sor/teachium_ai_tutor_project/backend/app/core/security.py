"""Sécurité : hachage des mots de passe (bcrypt) et jetons JWT."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

_DEV_SECRET_CACHE: dict[str, str] = {}

# Bcrypt tronque au-delà de 72 octets : on refuse explicitement plutôt que de
# laisser deux mots de passe différents devenir équivalents.
MAX_PASSWORD_BYTES = 72


class TokenError(Exception):
    """Jeton invalide, expiré ou mal formé."""


def _secret() -> str:
    if settings.jwt_secret:
        return settings.jwt_secret
    # Aucun JWT_SECRET fourni : on génère une clé éphémère pour ne pas planter au
    # démarrage, mais toutes les sessions sont invalidées à chaque redémarrage.
    if "value" not in _DEV_SECRET_CACHE:
        _DEV_SECRET_CACHE["value"] = secrets.token_urlsafe(48)
    return _DEV_SECRET_CACHE["value"]


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("Le mot de passe est trop long (72 octets maximum).")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | int, role: str, extra: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Session expirée. Veuillez vous reconnecter.") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Jeton d'authentification invalide.") from exc
