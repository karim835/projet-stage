"""Dépendances FastAPI : session base de données, utilisateur courant, contrôle de rôle."""

from __future__ import annotations

from typing import Annotated, Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.database import get_session_factory
from app.db.models import ROLE_ADMIN, ROLE_LEARNER, ROLE_TRAINER, Learner, User

bearer_scheme = HTTPBearer(auto_error=False, description="Jeton JWT obtenu via /api/auth/login")

DB_UNAVAILABLE = (
    "Base de données indisponible. Vérifiez la variable DATABASE_URL (Neon) "
    "et votre connexion Internet."
)


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL n'est pas configurée. Renseignez la chaîne Neon dans backend/.env.",
        )
    db = factory()
    try:
        yield db
    except SQLAlchemyError as exc:  # pragma: no cover - dépend du réseau
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DB_UNAVAILABLE) from exc
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not subject or not str(subject).isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide.")

    user = db.get(User, int(subject))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Compte introuvable.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce compte est désactivé.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    """Fabrique une dépendance qui n'autorise que certains rôles."""

    allowed = set(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas les droits nécessaires pour accéder à cette ressource.",
            )
        return user

    return dependency


require_learner = require_roles(ROLE_LEARNER)
require_trainer = require_roles(ROLE_TRAINER, ROLE_ADMIN)
require_admin = require_roles(ROLE_ADMIN)

TrainerUser = Annotated[User, Depends(require_trainer)]
AdminUser = Annotated[User, Depends(require_admin)]


def get_current_learner(user: CurrentUser, db: DbSession) -> Learner:
    """Fiche apprenant liée au compte connecté."""
    if user.role != ROLE_LEARNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette section est réservée aux comptes de type apprenant.",
        )
    learner = user.learner
    if learner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Aucune fiche apprenant n'est associée à ce compte. "
                "Cette section est réservée aux comptes de type apprenant."
            ),
        )
    return learner


CurrentLearner = Annotated[Learner, Depends(get_current_learner)]
