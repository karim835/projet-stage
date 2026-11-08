"""Routes de l'AI Tutor connecté : conversation persistée et recommandations."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select

from app.api.deps import CurrentLearner, DbSession
from app.db.models import Recommendation
from app.schemas.tutor import (
    ChatHistoryResponse,
    ChatMessageOut,
    RecommendationCompleteInput,
    RecommendationOut,
    TutorAskInput,
    TutorAskResponse,
)
from app.services import tutor_service
from app.services.tutor_service import EmptyQuestionError

router = APIRouter(tags=["AI Tutor"])


@router.post(
    "/api/chat/ask",
    response_model=TutorAskResponse,
    summary="Poser une question à l'AI Tutor (contexte apprenant + historique)",
)
def ask_tutor(payload: TutorAskInput, learner: CurrentLearner, db: DbSession):
    try:
        return tutor_service.ask(db, learner, payload.question)
    except EmptyQuestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/api/chat/history", response_model=ChatHistoryResponse, summary="Historique de conversation")
def history(learner: CurrentLearner, db: DbSession, limit: int = Query(200, ge=1, le=500)):
    engine = tutor_service.get_engine()
    messages = tutor_service.chat_history(db, learner.id, limit=limit)
    return ChatHistoryResponse(
        engine=engine.name,
        engine_label=engine.label,
        messages=[ChatMessageOut.model_validate(m) for m in messages],
    )


@router.delete("/api/chat/history", summary="Effacer sa conversation")
def clear_history(learner: CurrentLearner, db: DbSession):
    deleted = tutor_service.clear_history(db, learner.id)
    return {"deleted": deleted, "message": "Conversation effacée."}


@router.get(
    "/api/recommendations/me",
    response_model=list[RecommendationOut],
    summary="Recommandations en cours de l'apprenant connecté",
)
def my_recommendations(learner: CurrentLearner, db: DbSession):
    recos = tutor_service.active_recommendations(db, learner.id)
    if not recos:
        tutor_service.run_analysis(db, learner)
        recos = tutor_service.active_recommendations(db, learner.id)
    return [RecommendationOut.model_validate(r) for r in recos]


@router.get(
    "/api/recommendations/me/history",
    response_model=list[RecommendationOut],
    summary="Historique complet des recommandations",
)
def my_recommendation_history(learner: CurrentLearner, db: DbSession, limit: int = Query(100, ge=1, le=500)):
    rows = db.execute(
        select(Recommendation)
        .where(Recommendation.learner_id == learner.id)
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(limit)
    ).scalars()
    return [RecommendationOut.model_validate(r) for r in rows]


@router.post(
    "/api/recommendations/{recommendation_id}/complete",
    response_model=RecommendationOut,
    summary="Marquer une recommandation comme suivie",
)
def complete_recommendation(
    payload: RecommendationCompleteInput,
    learner: CurrentLearner,
    db: DbSession,
    recommendation_id: int = Path(..., ge=1),
):
    reco = db.get(Recommendation, recommendation_id)
    if reco is None or reco.learner_id != learner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommandation introuvable.")

    reco.completed = payload.completed
    reco.completed_at = dt.datetime.now(dt.timezone.utc) if payload.completed else None
    db.commit()
    db.refresh(reco)
    return RecommendationOut.model_validate(reco)
