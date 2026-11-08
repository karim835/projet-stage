"""Routes apprenants : fiche personnelle, liste formateur, détail, mise à jour."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentLearner, CurrentUser, DbSession, TrainerUser
from app.db.models import ROLE_ADMIN, ROLE_TRAINER, Learner, LearnerProfile, LearningActivity, User
from app.schemas.tutor import (
    ActivityOut,
    LearnerDashboard,
    LearnerDetail,
    LearnerListResponse,
    LearnerMetricsUpdate,
    LearnerSummary,
    ProfileSnapshot,
    RecommendationOut,
)
from app.services import stats_service, tutor_service

router = APIRouter(prefix="/api/learners", tags=["Apprenants"])


# --- Helpers ----------------------------------------------------------------


def _summary(learner: Learner, profile: LearnerProfile | None) -> LearnerSummary:
    return LearnerSummary(
        id=learner.id,
        student_id=learner.student_id,
        name=learner.display_name,
        email=learner.user.email if learner.user else None,
        course_category=learner.course_category,
        average_score=learner.average_score,
        completion_rate=learner.completion_rate,
        time_spent_hours=learner.time_spent_hours,
        quiz_attempts=learner.quiz_attempts,
        failed_quizzes=learner.failed_quizzes,
        login_frequency=learner.login_frequency,
        satisfaction_score=learner.satisfaction_score,
        profile=profile.profile if profile else None,
        risk_level=profile.risk_level if profile else None,
        has_account=learner.user_id is not None,
        updated_at=learner.updated_at,
    )


def _detail(db: DbSession, learner: Learner) -> LearnerDetail:
    profile = tutor_service.latest_profile(db, learner.id)
    if profile is None:
        profile = tutor_service.run_analysis(db, learner)

    recos = tutor_service.active_recommendations(db, learner.id)
    history = list(
        db.execute(
            select(LearnerProfile)
            .where(LearnerProfile.learner_id == learner.id)
            .order_by(LearnerProfile.created_at.desc(), LearnerProfile.id.desc())
            .limit(20)
        ).scalars()
    )

    base = _summary(learner, profile)
    return LearnerDetail(
        **base.model_dump(),
        completed_courses=learner.completed_courses,
        total_courses=learner.total_courses,
        reference_profile=learner.reference_profile,
        cluster=profile.cluster if profile else None,
        confidence=profile.confidence if profile else None,
        explanation=profile.explanation if profile else None,
        created_at=learner.created_at,
        recommendations=[RecommendationOut.model_validate(r) for r in recos],
        profile_history=[ProfileSnapshot.model_validate(p) for p in history],
        activities=[ActivityOut.model_validate(a) for a in learner.activities],
    )


def _promotion_reference(db: DbSession) -> dict:
    row = db.execute(
        select(
            func.count(Learner.id),
            func.avg(Learner.average_score),
            func.avg(Learner.completion_rate),
            func.avg(Learner.satisfaction_score),
            func.avg(Learner.time_spent_hours),
        )
    ).one()
    total, score, completion, satisfaction, time_spent = row
    return {
        "total_learners": int(total or 0),
        "average_score": round(float(score), 1) if score is not None else None,
        "average_completion_rate": round(float(completion), 1) if completion is not None else None,
        "average_satisfaction": round(float(satisfaction), 2) if satisfaction is not None else None,
        "average_time_spent": round(float(time_spent), 1) if time_spent is not None else None,
    }


def _load_learner_or_404(db: DbSession, learner_id: int) -> Learner:
    learner = db.execute(
        select(Learner).options(selectinload(Learner.user)).where(Learner.id == learner_id)
    ).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Apprenant introuvable.")
    return learner


# --- Routes apprenant -------------------------------------------------------


@router.get("/me", response_model=LearnerDashboard, summary="Tableau de bord de l'apprenant connecté")
def my_dashboard(learner: CurrentLearner, db: DbSession):
    return LearnerDashboard(learner=_detail(db, learner), stats_reference=_promotion_reference(db))


@router.post(
    "/me/analyze",
    response_model=LearnerDetail,
    summary="Relancer l'analyse ML sur ses propres données",
)
def analyze_me(learner: CurrentLearner, db: DbSession):
    tutor_service.run_analysis(db, learner)
    db.refresh(learner)
    return _detail(db, learner)


@router.get(
    "/me/activity",
    response_model=list[ActivityOut],
    summary="Historique d'activité de l'apprenant connecté",
)
def my_activity(learner: CurrentLearner, db: DbSession, limit: int = Query(100, ge=1, le=500)):
    rows = db.execute(
        select(LearningActivity)
        .where(LearningActivity.learner_id == learner.id)
        .order_by(LearningActivity.created_at.asc(), LearningActivity.id.asc())
        .limit(limit)
    ).scalars()
    return [ActivityOut.model_validate(a) for a in rows]


# NOTE — L'enregistrement d'une note par l'apprenant lui-même a été volontairement
# supprimé : un apprenant ne peut pas s'auto-attribuer une note. Les notes ne
# proviennent plus que de deux sources contrôlées par le serveur :
#   1. la correction automatique d'un quiz passé dans l'application
#      (POST /api/quizzes/{id}/submit, voir app/api/routes/quizzes.py) ;
#   2. la saisie d'une évaluation hors ligne par un FORMATEUR
#      (POST /api/learners/{id}/evaluations).
# La route ci-dessus reste en lecture seule pour consulter son historique.


# --- Routes formateur / administrateur --------------------------------------


@router.get("", response_model=LearnerListResponse, summary="Lister les apprenants (formateur)")
def list_learners(
    db: DbSession,
    _: TrainerUser,
    search: Optional[str] = Query(None, max_length=80, description="Nom, e-mail ou identifiant"),
    profile: Optional[str] = Query(None, max_length=40, description="Filtrer par profil courant"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    min_completion: Optional[float] = Query(None, ge=0, le=100),
    max_completion: Optional[float] = Query(None, ge=0, le=100),
    max_login_frequency: Optional[int] = Query(
        None, ge=0, le=100, description="Apprenants peu actifs : connexions/semaine ≤ valeur"
    ),
    sort_by: str = Query("average_score", pattern="^(average_score|completion_rate|student_id|satisfaction_score|time_spent_hours|failed_quizzes)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    sub = stats_service.latest_profile_subquery()
    stmt = (
        select(Learner, LearnerProfile)
        .options(selectinload(Learner.user))
        .outerjoin(sub, sub.c.learner_id == Learner.id)
        .outerjoin(LearnerProfile, LearnerProfile.id == sub.c.profile_id)
    )

    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.outerjoin(User, User.id == Learner.user_id).where(
            or_(
                func.lower(Learner.student_id).like(pattern),
                func.lower(func.coalesce(User.name, "")).like(pattern),
                func.lower(func.coalesce(User.email, "")).like(pattern),
            )
        )
    if profile:
        stmt = stmt.where(LearnerProfile.profile == profile)
    if min_score is not None:
        stmt = stmt.where(Learner.average_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(Learner.average_score <= max_score)
    if min_completion is not None:
        stmt = stmt.where(Learner.completion_rate >= min_completion)
    if max_completion is not None:
        stmt = stmt.where(Learner.completion_rate <= max_completion)
    if max_login_frequency is not None:
        stmt = stmt.where(Learner.login_frequency <= max_login_frequency)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    column = getattr(Learner, sort_by)
    stmt = stmt.order_by(column.asc() if sort_dir == "asc" else column.desc(), Learner.id.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows = db.execute(stmt).all()
    return LearnerListResponse(
        total=int(total),
        page=page,
        page_size=page_size,
        items=[_summary(learner, prof) for learner, prof in rows],
    )


@router.get("/{learner_id}", response_model=LearnerDetail, summary="Détail d'un apprenant")
def learner_detail(
    db: DbSession,
    user: CurrentUser,
    learner_id: int = Path(..., ge=1),
):
    learner = _load_learner_or_404(db, learner_id)
    # Un apprenant ne peut consulter que sa propre fiche.
    if user.role not in (ROLE_TRAINER, ROLE_ADMIN) and learner.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez consulter que votre propre fiche apprenant.",
        )
    return _detail(db, learner)


@router.patch(
    "/{learner_id}",
    response_model=LearnerDetail,
    summary="Mettre à jour les indicateurs d'un apprenant (formateur)",
)
def update_learner(
    payload: LearnerMetricsUpdate,
    db: DbSession,
    _: TrainerUser,
    learner_id: int = Path(..., ge=1),
):
    learner = _load_learner_or_404(db, learner_id)
    _apply_metrics(learner, payload)
    db.commit()
    db.refresh(learner)
    tutor_service.run_analysis(db, learner)
    return _detail(db, learner)


@router.post(
    "/{learner_id}/analyze",
    response_model=LearnerDetail,
    summary="Relancer l'analyse ML d'un apprenant (formateur)",
)
def analyze_learner(
    db: DbSession,
    _: TrainerUser,
    learner_id: int = Path(..., ge=1),
):
    learner = _load_learner_or_404(db, learner_id)
    tutor_service.run_analysis(db, learner)
    db.refresh(learner)
    return _detail(db, learner)


def _apply_metrics(learner: Learner, payload: LearnerMetricsUpdate) -> None:
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun champ à mettre à jour n'a été fourni.",
        )
    for key, value in data.items():
        setattr(learner, key, value)
    if learner.total_courses and learner.completed_courses > learner.total_courses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le nombre de cours terminés ne peut pas dépasser le nombre total de cours.",
        )
