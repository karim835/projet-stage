"""Routes de la bibliothèque de cours.

Lecture ouverte à tout utilisateur connecté (les apprenants consultent les
fiches). Écriture réservée aux formateurs et administrateurs.

Ces fiches constituent la base de connaissances interrogée par l'AI Tutor
(recherche TF-IDF, voir `app/services/knowledge_service.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentLearner, CurrentUser, DbSession, TrainerUser
from app.db.models import CourseResource
from app.schemas.quiz import (
    CourseCard,
    CourseCompletionResponse,
    CourseInput,
    CourseOut,
    CourseSearchHit,
    CourseUpdate,
)
from app.services import knowledge_service, lesson_service, quiz_service

router = APIRouter(prefix="/api/courses", tags=["Bibliothèque de cours"])


@router.get("", response_model=list[CourseCard], summary="Lister les fiches de cours")
def list_courses(
    db: DbSession,
    user: CurrentUser,
    category: str | None = Query(None, max_length=60),
    level: str | None = Query(None, max_length=20),
    search: str | None = Query(None, max_length=120),
):
    stmt = select(CourseResource)
    if category:
        stmt = stmt.where(CourseResource.category == category)
    if level:
        stmt = stmt.where(CourseResource.level == level)
    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(CourseResource.title).like(pattern),
                func.lower(func.coalesce(CourseResource.keywords, "")).like(pattern),
                func.lower(func.coalesce(CourseResource.summary, "")).like(pattern),
            )
        )
    rows = list(db.execute(stmt.order_by(CourseResource.category, CourseResource.title)).scalars())
    completions = (
        lesson_service.completion_map(db, user.learner.id, [row.id for row in rows])
        if user.learner is not None
        else {}
    )
    return [
        CourseCard.model_validate(row).model_copy(
            update={
                "completed": row.id in completions,
                "completed_at": (
                    completions[row.id].completed_at if row.id in completions else None
                ),
                "recommended_quiz_id": (
                    completions[row.id].recommended_quiz_id if row.id in completions else None
                ),
            }
        )
        for row in rows
    ]


@router.get("/categories", summary="Filières disponibles dans la bibliothèque")
def list_categories(db: DbSession, _: CurrentUser):
    rows = db.execute(
        select(CourseResource.category, func.count(CourseResource.id))
        .group_by(CourseResource.category)
        .order_by(CourseResource.category)
    ).all()
    return [{"category": category, "count": int(count)} for category, count in rows]


@router.get("/search", response_model=list[CourseSearchHit], summary="Recherche par pertinence (TF-IDF)")
def search_courses(
    db: DbSession,
    _: CurrentUser,
    q: str = Query(..., min_length=2, max_length=300),
    limit: int = Query(5, ge=1, le=20),
    category: str | None = Query(None, max_length=60),
):
    """Même moteur de recherche que celui utilisé par l'AI Tutor."""
    hits = knowledge_service.search(db, q, top_k=limit, category=category)
    return [
        CourseSearchHit(
            id=hit["resource"].id,
            title=hit["resource"].title,
            category=hit["resource"].category,
            level=hit["resource"].level,
            score=round(hit["score"], 4),
            passage=knowledge_service.best_passage(hit["resource"], q, max_chars=400),
        )
        for hit in hits
    ]


@router.get("/{course_id}", response_model=CourseOut, summary="Lire une fiche complète")
def course_detail(db: DbSession, user: CurrentUser, course_id: int = Path(..., ge=1)):
    course = db.get(CourseResource, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fiche de cours introuvable.")
    completion = None
    if user.learner is not None:
        completion = lesson_service.completion_map(db, user.learner.id, [course.id]).get(course.id)
    recommended_quiz = None
    if completion is not None and completion.recommended_quiz_id is not None:
        recommended_quiz = next(
            (
                item
                for item in quiz_service.available_quizzes(db, user.learner)
                if item["id"] == completion.recommended_quiz_id and item["question_count"] > 0
            ),
            None,
        )
    return CourseOut.model_validate(course).model_copy(
        update={
            "completed": completion is not None,
            "completed_at": completion.completed_at if completion is not None else None,
            "recommended_quiz": recommended_quiz,
        }
    )


@router.post(
    "/{course_id}/complete",
    response_model=CourseCompletionResponse,
    summary="Confirmer qu'une fiche de cours est terminée",
)
def complete_course(
    db: DbSession,
    learner: CurrentLearner,
    course_id: int = Path(..., ge=1),
):
    course = db.get(CourseResource, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fiche de cours introuvable.")
    return lesson_service.complete_course(db, learner, course)


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED, summary="Créer une fiche")
def create_course(payload: CourseInput, db: DbSession, user: TrainerUser):
    course = CourseResource(
        title=payload.title.strip(),
        category=payload.category.strip(),
        summary=(payload.summary or "").strip() or None,
        content=payload.content.strip(),
        keywords=(payload.keywords or "").strip() or None,
        level=payload.level,
        created_by_id=user.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    knowledge_service.invalidate()  # l'index TF-IDF doit être reconstruit
    return CourseOut.model_validate(course)


@router.patch("/{course_id}", response_model=CourseOut, summary="Modifier une fiche")
def update_course(
    payload: CourseUpdate, db: DbSession, _: TrainerUser, course_id: int = Path(..., ge=1)
):
    course = db.get(CourseResource, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fiche de cours introuvable.")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie."
        )
    for key, value in data.items():
        setattr(course, key, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(course)
    knowledge_service.invalidate()
    return CourseOut.model_validate(course)


@router.delete("/{course_id}", summary="Supprimer une fiche")
def delete_course(db: DbSession, _: TrainerUser, course_id: int = Path(..., ge=1)):
    course = db.get(CourseResource, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fiche de cours introuvable.")
    title = course.title
    db.delete(course)
    db.commit()
    knowledge_service.invalidate()
    return {"message": f"Fiche « {title} » supprimée de la bibliothèque."}
