"""Connexion SQLAlchemy vers PostgreSQL hébergé sur Neon.

Aucune installation locale de PostgreSQL n'est nécessaire : l'application ouvre
une connexion réseau chiffrée (TLS) vers l'instance Neon indiquée par la
variable d'environnement `DATABASE_URL`.
"""

from __future__ import annotations

import logging
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("teachium.db")


class Base(DeclarativeBase):
    """Classe de base des modèles ORM."""


_engine = None
_SessionLocal = None


def _build_engine():
    """Crée le moteur SQLAlchemy adapté à Neon (connexions serverless)."""
    if not settings.database_configured:
        return None

    kwargs: dict = {
        "echo": settings.sql_echo,
        "future": True,
        # Neon ferme les connexions inactives : on vérifie la connexion avant
        # chaque emprunt au pool et on recycle régulièrement.
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    if settings.database_url.startswith("postgresql"):
        kwargs.update({"pool_size": 5, "max_overflow": 5, "pool_timeout": 30})
        # 20 s : une instance Neon en veille met quelques secondes à démarrer
        # lors de la toute première requête (cold start).
        kwargs["connect_args"] = {"connect_timeout": 20, "application_name": "teachium-ai-tutor"}

    return create_engine(settings.database_url, **kwargs)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        if engine is None:
            return None
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionLocal


def reset_engine() -> None:
    """Réinitialise le moteur (utilisé par les tests et les scripts)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def session_scope() -> Session:
    """Ouvre une session hors contexte FastAPI (scripts, tests)."""
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError(
            "DATABASE_URL n'est pas configurée. Renseignez la chaîne de connexion Neon dans backend/.env."
        )
    return factory()


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, fermée dans tous les cas."""
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL n'est pas configurée.")
    db = factory()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> tuple[bool, str]:
    """Teste la connexion et renvoie (ok, message lisible par un humain)."""
    if not settings.database_configured:
        return False, "DATABASE_URL n'est pas définie (voir backend/.env.example)."
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, f"Connecté à {settings.safe_database_target()}"
    except SQLAlchemyError as exc:
        logger.warning("Connexion base de données indisponible: %s", exc.__class__.__name__)
        return False, "Base de données injoignable. Vérifiez DATABASE_URL et votre connexion Internet."


def create_all() -> None:
    """Crée les tables et applique les petites évolutions compatibles.

    Le prototype historique n'utilise pas Alembic. ``create_all`` sait créer
    une base neuve mais n'ajoute pas de colonnes à une base Neon existante.
    Les ajouts ci-dessous sont donc exécutés explicitement et de façon
    idempotente afin qu'une ancienne installation puisse être mise à niveau en
    relançant simplement ``scripts/init_database.py``.
    """
    from app.db import models  # noqa: F401  (enregistre les modèles sur Base.metadata)

    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL n'est pas configurée.")
    Base.metadata.create_all(bind=engine)
    _apply_compatible_schema_upgrades(engine)


def _apply_compatible_schema_upgrades(engine) -> None:
    """Ajoute uniquement des colonnes nullable, sans détruire de données.

    Cette migration légère couvre les installations créées avant l'ajout du
    coaching de quiz. Elle fonctionne sur PostgreSQL/Neon et sur SQLite, ce qui
    garde les tests locaux simples.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    if "quiz_questions" in table_names:
        question_columns = {
            column["name"] for column in inspector.get_columns("quiz_questions")
        }
        if "concept" not in question_columns:
            statements.append("ALTER TABLE quiz_questions ADD COLUMN concept VARCHAR(120)")
        if "hint" not in question_columns:
            statements.append("ALTER TABLE quiz_questions ADD COLUMN hint TEXT")

    if "quizzes" in table_names:
        quiz_columns = {column["name"] for column in inspector.get_columns("quizzes")}
        if "course_resource_id" not in quiz_columns:
            statements.append("ALTER TABLE quizzes ADD COLUMN course_resource_id INTEGER")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Schéma pédagogique mis à niveau (%s évolution(s)).", len(statements))

    # PostgreSQL et SQLite acceptent tous deux IF NOT EXISTS pour les index sur
    # les versions prises en charge par le projet.
    with engine.begin() as connection:
        if "quiz_questions" in table_names:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_quiz_questions_concept ON quiz_questions (concept)")
            )
        if "quizzes" in table_names:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_quizzes_course_resource_id "
                     "ON quizzes (course_resource_id)")
            )
