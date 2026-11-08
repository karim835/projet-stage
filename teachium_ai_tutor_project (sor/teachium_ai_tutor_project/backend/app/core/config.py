"""Configuration centrale de l'application TEACHIUM AI Tutor.

Toutes les valeurs sensibles (URL de base de données, clé JWT) sont lues depuis
les variables d'environnement ou depuis le fichier `backend/.env`.
Aucun identifiant n'est écrit en dur dans le code source.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


def _load_env_file(path: Path) -> None:
    """Charge un fichier .env minimaliste sans dépendance externe.

    Les variables déjà présentes dans l'environnement système ne sont jamais
    écrasées : l'environnement réel reste prioritaire sur le fichier.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(ENV_FILE)


def normalize_database_url(url: str) -> str:
    """Rend une URL Neon/PostgreSQL utilisable par SQLAlchemy + psycopg2.

    - `postgres://` (format historique) devient `postgresql+psycopg2://`
    - `postgresql://` reçoit explicitement le driver psycopg2
    - `sslmode=require` est ajouté si absent (obligatoire sur Neon)
    - `channel_binding` est retiré : ce paramètre est envoyé par la console Neon
      mais n'est pas accepté par toutes les versions de libpq embarquées dans
      psycopg2-binary, et il n'est pas nécessaire au chiffrement TLS.
    """
    if not url:
        return url

    url = url.strip().strip('"').strip("'")

    # Les tests hors ligne utilisent ponctuellement SQLite. Cette fonction ne
    # doit normaliser que PostgreSQL/Neon : ``urlunsplit`` réduirait sinon les
    # trois barres d'une URL SQLite absolue et produirait une URL invalide.
    if not url.startswith(("postgres://", "postgresql://", "postgresql+")):
        return url

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "channel_binding"]

    is_postgres = parts.scheme.startswith("postgresql")
    is_local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if is_postgres and not is_local and not any(k == "sslmode" for k, _ in query):
        query.append(("sslmode", "require"))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings:
    """Paramètres applicatifs résolus au démarrage."""

    def __init__(self) -> None:
        self.app_name: str = "TEACHIUM AI Tutor API"
        self.app_version: str = "2.0.0"

        raw_url = os.getenv("DATABASE_URL", "").strip()
        self.database_url_raw: str = raw_url
        self.database_url: str = normalize_database_url(raw_url)
        self.database_configured: bool = bool(self.database_url)

        self.jwt_secret: str = os.getenv("JWT_SECRET", "").strip()
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256").strip() or "HS256"
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))

        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        self.cors_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]

        # Réservé à une future intégration LLM. Non requis par le prototype.
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model: str = os.getenv("LLM_MODEL", "").strip()

        self.sql_echo: bool = os.getenv("SQL_ECHO", "false").lower() in {"1", "true", "yes"}

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    def safe_database_target(self) -> str:
        """Description non sensible de la cible SQL (jamais le mot de passe)."""
        if not self.database_url:
            return "non configurée"
        parts = urlsplit(self.database_url)
        host = parts.hostname or "?"
        db = (parts.path or "/").lstrip("/") or "?"
        return f"{host}/{db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
