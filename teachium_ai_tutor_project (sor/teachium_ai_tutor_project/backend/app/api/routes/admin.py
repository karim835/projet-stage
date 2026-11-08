"""Routes d'administration : comptes, activité système, recommandations."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.db.models import ROLE_ADMIN, Learner, Recommendation, User
from app.schemas.auth import UserUpdateInput, UserWithLearner
from app.schemas.tutor import RecommendationOut, SystemEvent
from app.services import stats_service

router = APIRouter(prefix="/api/admin", tags=["Administration"])


class UserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserWithLearner]


class DeleteConfirmation(BaseModel):
    """Confirmation explicite exigée pour toute suppression définitive."""

    confirm_email: str = Field(
        ..., description="Saisir exactement l'adresse e-mail du compte pour confirmer la suppression"
    )


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


def _count_active_admins(db: DbSession) -> int:
    return int(
        db.execute(
            select(func.count(User.id)).where(User.role == ROLE_ADMIN, User.is_active.is_(True))
        ).scalar_one()
    )


@router.get("/overview", summary="Vue d'ensemble du système")
def overview(db: DbSession, _: AdminUser):
    return stats_service.admin_overview(db)


@router.get("/activity", response_model=list[SystemEvent], summary="Activité récente réelle du système")
def activity(db: DbSession, _: AdminUser, limit: int = Query(25, ge=1, le=100)):
    return stats_service.system_activity(db, limit=limit)


@router.get("/users", response_model=UserListResponse, summary="Lister les comptes")
def list_users(
    db: DbSession,
    _: AdminUser,
    search: Optional[str] = Query(None, max_length=80),
    role: Optional[str] = Query(None, pattern="^(learner|trainer|administrator)$"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    stmt = select(User).options(selectinload(User.learner))
    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.name).like(pattern), func.lower(User.email).like(pattern))
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    users = db.execute(stmt).scalars().all()

    return UserListResponse(
        total=int(total), page=page, page_size=page_size, items=[_to_public(u) for u in users]
    )


@router.patch("/users/{user_id}", response_model=UserWithLearner, summary="Modifier un compte")
def update_user(
    payload: UserUpdateInput,
    db: DbSession,
    admin: AdminUser,
    user_id: int = Path(..., ge=1),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie."
        )

    # Garde-fous : ne jamais se verrouiller hors de l'administration.
    if user.id == admin.id and data.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas désactiver votre propre compte."
        )
    if user.id == admin.id and data.get("role") and data["role"] != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas modifier votre propre rôle."
        )
    losing_admin = user.role == ROLE_ADMIN and (
        data.get("is_active") is False or (data.get("role") and data["role"] != ROLE_ADMIN)
    )
    if losing_admin and _count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible : ce compte est le dernier administrateur actif.",
        )

    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return _to_public(user)


@router.post(
    "/users/{user_id}/delete",
    summary="Supprimer définitivement un compte (confirmation obligatoire)",
)
def delete_user(
    payload: DeleteConfirmation,
    db: DbSession,
    admin: AdminUser,
    user_id: int = Path(..., ge=1),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas supprimer votre propre compte."
        )
    if payload.confirm_email.strip().lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'adresse e-mail de confirmation ne correspond pas au compte à supprimer.",
        )
    if user.role == ROLE_ADMIN and _count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible : ce compte est le dernier administrateur actif.",
        )

    email = user.email
    db.delete(user)
    db.commit()
    return {"message": f"Le compte {email} et sa fiche apprenant associée ont été supprimés."}


@router.get(
    "/recommendations",
    response_model=list[RecommendationOut],
    summary="Dernières recommandations générées",
)
def recent_recommendations(db: DbSession, _: AdminUser, limit: int = Query(50, ge=1, le=200)):
    rows = db.execute(
        select(Recommendation).order_by(Recommendation.created_at.desc(), Recommendation.id.desc()).limit(limit)
    ).scalars()
    return [RecommendationOut.model_validate(r) for r in rows]


@router.get("/learners/unlinked", summary="Apprenants importés sans compte de connexion")
def unlinked_learners(db: DbSession, _: AdminUser, limit: int = Query(50, ge=1, le=500)):
    rows = db.execute(
        select(Learner).where(Learner.user_id.is_(None)).order_by(Learner.student_id).limit(limit)
    ).scalars()
    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "average_score": r.average_score,
            "completion_rate": r.completion_rate,
            "reference_profile": r.reference_profile,
        }
        for r in rows
    ]
