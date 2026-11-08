"""Routes ML sans état : analyse de profil, recommandation, chatbot.

Ces trois endpoints existaient déjà dans le prototype initial et sont conservés
tels quels (mêmes chemins, mêmes schémas). Ils restent accessibles sans
authentification : ils ne lisent aucune donnée personnelle et servent de
démonstration directe des modèles dans Swagger.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.learner import (
    ChatbotInput,
    ChatbotResponse,
    LearnerInput,
    ProfileResponse,
    RecommendationInput,
    RecommendationResponse,
)
from app.services.chatbot_service import chatbot_response
from app.services.profile_service import analyze_profile
from app.services.recommendation_service import recommend_content
from app.services.tutor_service import get_engine

router = APIRouter(tags=["Modèles IA (sans état)"])


@router.post(
    "/api/profile/analyze",
    response_model=ProfileResponse,
    summary="Analyser un profil apprenant (K-Means + Decision Tree)",
)
def profile_analyze(payload: LearnerInput):
    try:
        return analyze_profile(payload.model_dump())
    except FileNotFoundError as exc:  # pragma: no cover - artefacts absents
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modèle indisponible. Exécutez scripts/train_models.py pour régénérer les fichiers .joblib.",
        ) from exc


@router.post(
    "/api/recommendations",
    response_model=RecommendationResponse,
    summary="Générer des recommandations pédagogiques",
)
def recommendations(payload: RecommendationInput):
    return recommend_content(**payload.model_dump())


@router.post(
    "/api/chatbot/ask",
    response_model=ChatbotResponse,
    summary="Poser une question au tuteur (mode sans état)",
)
def chatbot_ask(payload: ChatbotInput):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La question ne peut pas être vide.",
        )
    answer = chatbot_response(
        question=question,
        profile=payload.profile,
        recommended_content=payload.recommended_content,
    )
    return {"answer": answer}


@router.get("/api/tutor/engine", summary="Nature du moteur conversationnel utilisé")
def tutor_engine():
    engine = get_engine()
    return {
        "engine": engine.name,
        "label": engine.label,
        "is_llm": engine.name == "llm",
        "note": (
            "Le tuteur repose sur une analyse par mots-clés couplée aux modèles "
            "scikit-learn du projet. Il ne s'agit pas d'un grand modèle de langage."
        ),
    }
