from pydantic import BaseModel, Field
from typing import List, Optional


class LearnerInput(BaseModel):
    average_score: float = Field(..., ge=0, le=100, description="Score moyen de l'apprenant")
    time_spent_hours: float = Field(..., ge=0, description="Temps passé sur la plateforme")
    completion_rate: float = Field(..., ge=0, le=100, description="Taux de complétion des cours")
    quiz_attempts: int = Field(..., ge=0, description="Nombre de quiz passés")
    failed_quizzes: int = Field(..., ge=0, description="Nombre de quiz échoués")
    login_frequency: int = Field(..., ge=0, description="Nombre moyen de connexions par semaine")
    satisfaction_score: Optional[float] = Field(3.0, ge=1, le=5, description="Satisfaction de 1 à 5")


class ProfileResponse(BaseModel):
    profile: str
    cluster: Optional[int] = None
    confidence: Optional[float] = Field(
        None, description="Probabilité de la classe prédite par l'arbre de décision (0 à 1)"
    )
    source: Optional[str] = Field(
        None, description="'model' si l'arbre entraîné a été utilisé, 'rules' pour le repli interprétable"
    )
    risk_level: str
    explanation: str


class RecommendationInput(BaseModel):
    profile: str
    average_score: float = Field(..., ge=0, le=100)
    completion_rate: float = Field(..., ge=0, le=100)
    failed_quizzes: int = Field(..., ge=0)
    satisfaction_score: Optional[float] = Field(3.0, ge=1, le=5)


class RecommendationResponse(BaseModel):
    recommended_content: List[str]
    reason: str
    priority: str


class ChatbotInput(BaseModel):
    question: str
    profile: str
    recommended_content: Optional[str] = None


class ChatbotResponse(BaseModel):
    answer: str
