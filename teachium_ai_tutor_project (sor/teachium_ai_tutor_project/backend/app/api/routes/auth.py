"""Routes d'authentification : inscription, connexion, profil du compte connecté."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import ROLE_LEARNER, Learner, User
from app.schemas.auth import (
    LoginInput,
    PasswordChangeInput,
    RegisterInput,
    TokenResponse,
    UserWithLearner,
)

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


def _next_student_id(db: DbSession) -> str:
    """Identifiant apprenant unique, dans la continuité du dataset (STU0001...)."""
    last = db.execute(select(func.max(Learner.student_id))).scalar()
    if last and last.startswith("STU") and last[3:].isdigit():
        return f"STU{int(last[3:]) + 1:04d}"
    count = db.execute(select(func.count(Learner.id))).scalar_one()
    return f"STU{int(count) + 1:04d}"


def _to_public(user: User) -> UserWithLearner:
    learner = user.learner
    return UserWithLearner(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        learner_id=learner.id if learner else None,
        student_id=learner.student_id if learner else None,
    )


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, {"email": user.email}),
        expires_in_minutes=settings.jwt_expire_minutes,
        user=_to_public(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
def register(payload: RegisterInput, db: DbSession):
    email = payload.email.lower().strip()
    existing = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse e-mail.",
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # L'inscription publique crée toujours un apprenant. Les comptes élevés
    # sont exclusivement gérés depuis l'espace administrateur.
    user = User(name=payload.name, email=email, password_hash=password_hash, role=ROLE_LEARNER)
    db.add(user)
    db.flush()

    # Le quiz n'est pas attribué ici : il sera proposé après la confirmation
    # de lecture d'une fiche, ce qui garantit qu'il correspond au cours suivi.
    db.add(
        Learner(
            user_id=user.id,
            student_id=_next_student_id(db),
            course_category=payload.course_category,
        )
    )

    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=TokenResponse, summary="Se connecter")
def login(payload: LoginInput, db: DbSession):
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()

    # Message volontairement identique dans les deux cas pour ne pas révéler
    # quelles adresses existent en base.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse e-mail ou mot de passe incorrect.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce compte est désactivé.")

    return _token_for(user)


@router.get("/me", response_model=UserWithLearner, summary="Compte connecté")
def me(user: CurrentUser):
    return _to_public(user)


@router.post("/change-password", status_code=status.HTTP_200_OK, summary="Changer son mot de passe")
def change_password(payload: PasswordChangeInput, user: CurrentUser, db: DbSession):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Le mot de passe actuel est incorrect."
        )
    try:
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    return {"message": "Mot de passe mis à jour."}
