from fastapi import FastAPI
from app.schemas.learner import (
    LearnerInput,
    ProfileResponse,
    RecommendationInput,
    RecommendationResponse,
    ChatbotInput,
    ChatbotResponse,
)
from app.services.profile_service import analyze_profile
from app.services.recommendation_service import recommend_content
from app.services.chatbot_service import chatbot_response
from app.services.data_service import dashboard_stats, model_metrics

app = FastAPI(
    title="TEACHIUM AI Tutor API",
    description="API REST pour un système de tutorat intelligent basé sur l'IA.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {"message": "TEACHIUM AI Tutor API is running"}


@app.post("/api/profile/analyze", response_model=ProfileResponse)
def profile_analyze(payload: LearnerInput):
    return analyze_profile(payload.model_dump())


@app.post("/api/recommendations", response_model=RecommendationResponse)
def recommendations(payload: RecommendationInput):
    return recommend_content(**payload.model_dump())


@app.post("/api/chatbot/ask", response_model=ChatbotResponse)
def chatbot_ask(payload: ChatbotInput):
    answer = chatbot_response(
        question=payload.question,
        profile=payload.profile,
        recommended_content=payload.recommended_content,
    )
    return {"answer": answer}


@app.get("/api/dashboard/stats")
def stats():
    return dashboard_stats()


@app.get("/api/model/evaluate")
def evaluate():
    return model_metrics()
