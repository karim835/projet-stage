"""Tests de la couche base de données et de la configuration Neon."""

from __future__ import annotations

from sqlalchemy import inspect

from app.core.config import normalize_database_url, settings
from app.db.database import check_connection, get_engine

EXPECTED_TABLES = {
    "users",
    "learners",
    "learner_profiles",
    "recommendations",
    "learning_activity",
    "chat_messages",
    "course_completions",
}


# --- Normalisation d'URL (aucune connexion requise) --------------------------


def test_neon_url_gets_psycopg2_driver_and_ssl():
    url = normalize_database_url(
        "postgresql://user:pass@ep-demo-123.eu-central-1.aws.neon.tech/neondb"
    )
    assert url.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in url


def test_legacy_postgres_scheme_is_upgraded():
    url = normalize_database_url("postgres://user:pass@ep-demo.aws.neon.tech/neondb")
    assert url.startswith("postgresql+psycopg2://")


def test_channel_binding_is_removed():
    """Neon propose channel_binding=require, que libpq n'accepte pas partout."""
    url = normalize_database_url(
        "postgresql://u:p@ep-x.aws.neon.tech/db?sslmode=require&channel_binding=require"
    )
    assert "channel_binding" not in url
    assert "sslmode=require" in url


def test_existing_sslmode_is_preserved():
    url = normalize_database_url("postgresql://u:p@ep-x.aws.neon.tech/db?sslmode=verify-full")
    assert "sslmode=verify-full" in url
    assert url.count("sslmode") == 1


def test_local_url_does_not_force_ssl():
    url = normalize_database_url("postgresql://u:p@localhost:5432/db")
    assert "sslmode" not in url


def test_non_postgres_url_is_preserved_for_offline_tests():
    url = "sqlite:///C:/tmp/teachium-test.sqlite3"
    assert normalize_database_url(url) == url


def test_credentials_are_never_exposed_in_safe_target():
    """`safe_database_target()` sert aux logs et à /health : jamais de mot de passe."""
    target = settings.safe_database_target()
    if settings.database_url.startswith("postgresql"):
        password = settings.database_url.split("://", 1)[1].split("@", 1)[0]
        if ":" in password:
            assert password.split(":", 1)[1] not in target


def test_no_hardcoded_credentials_in_source():
    """Aucune chaîne de connexion ne doit être écrite en dur dans le code."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    offenders = []
    for path in (backend / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in ("postgresql://", "postgres://"):
            for line in text.splitlines():
                if marker in line and "neon.tech" in line and "example" not in line.lower():
                    offenders.append(f"{path.name}: {line.strip()[:80]}")
    assert not offenders, f"Identifiants en dur détectés : {offenders}"


# --- Connexion réelle --------------------------------------------------------


def test_connection_and_schema(require_db):
    ok, message = check_connection()
    assert ok, message

    tables = set(inspect(get_engine()).get_table_names())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Tables manquantes : {missing}"


def test_indexes_exist(require_db):
    inspector = inspect(get_engine())
    indexed = {idx["name"] for idx in inspector.get_indexes("learner_profiles")}
    assert any("learner" in name for name in indexed)


def test_health_reports_database(client, require_db):
    body = client.get("/health").json()
    assert body["database"]["configured"] is True
    assert body["database"]["connected"] is True
