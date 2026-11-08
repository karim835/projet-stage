"""Schémas Pydantic pour les apprenants, recommandations, chat et tableaux de bord."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Apprenants -------------------------------------------------------------


class LearnerMetrics(BaseModel):
    """Indicateurs pédagogiques modifiables d'un apprenant."""

    average_score: float = Field(..., ge=0, le=100)
    completion_rate: float = Field(..., ge=0, le=100)
    time_spent_hours: float = Field(..., ge=0, le=10000)
    quiz_attempts: int = Field(..., ge=0, le=1000)
    failed_quizzes: int = Field(..., ge=0, le=1000)
    login_frequency: int = Field(..., ge=0, le=100)
    satisfaction_score: float = Field(3.0, ge=1, le=5)
    completed_courses: int = Field(0, ge=0, le=1000)
    total_courses: int = Field(0, ge=0, le=1000)
    course_category: Optional[str] = Field(None, max_length=60)


class LearnerMetricsUpdate(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont modifiés."""

    average_score: Optional[float] = Field(None, ge=0, le=100)
    completion_rate: Optional[float] = Field(None, ge=0, le=100)
    time_spent_hours: Optional[float] = Field(None, ge=0, le=10000)
    quiz_attempts: Optional[int] = Field(None, ge=0, le=1000)
    failed_quizzes: Optional[int] = Field(None, ge=0, le=1000)
    login_frequency: Optional[int] = Field(None, ge=0, le=100)
    satisfaction_score: Optional[float] = Field(None, ge=1, le=5)
    completed_courses: Optional[int] = Field(None, ge=0, le=1000)
    total_courses: Optional[int] = Field(None, ge=0, le=1000)
    course_category: Optional[str] = Field(None, max_length=60)


class ProfileSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile: str
    cluster: Optional[int] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    explanation: Optional[str] = None
    source: str
    created_at: dt.datetime


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    reason: Optional[str] = None
    priority: Optional[str] = None
    profile: Optional[str] = None
    completed: bool
    completed_at: Optional[dt.datetime] = None
    created_at: dt.datetime


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_type: str
    title: Optional[str] = None
    score: Optional[float] = None
    duration_minutes: Optional[float] = None
    created_at: dt.datetime


class LearnerSummary(BaseModel):
    """Ligne du tableau formateur."""

    id: int
    student_id: str
    name: str
    email: Optional[str] = None
    course_category: Optional[str] = None
    average_score: float
    completion_rate: float
    time_spent_hours: float
    quiz_attempts: int
    failed_quizzes: int
    login_frequency: int
    satisfaction_score: float
    profile: Optional[str] = None
    risk_level: Optional[str] = None
    has_account: bool
    updated_at: dt.datetime


class LearnerDetail(LearnerSummary):
    completed_courses: int
    total_courses: int
    reference_profile: Optional[str] = None
    cluster: Optional[int] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    created_at: dt.datetime
    recommendations: list[RecommendationOut] = []
    profile_history: list[ProfileSnapshot] = []
    activities: list[ActivityOut] = []


class LearnerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LearnerSummary]


class RecommendationCompleteInput(BaseModel):
    completed: bool = True


# --- AI Tutor ---------------------------------------------------------------


class TutorAskInput(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class TutorAskResponse(BaseModel):
    answer: str
    profile: str
    engine: str
    engine_label: str


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    message: str
    created_at: dt.datetime


class ChatHistoryResponse(BaseModel):
    engine: str
    engine_label: str
    messages: list[ChatMessageOut]


# --- Tableaux de bord -------------------------------------------------------


class ScoreBucket(BaseModel):
    range: str
    count: int


class ProfilePerformance(BaseModel):
    profile: str
    learners: int
    average_score: Optional[float] = None
    average_completion: Optional[float] = None
    average_satisfaction: Optional[float] = None
    average_time_spent: Optional[float] = None


class DashboardStats(BaseModel):
    source: str
    total_learners: int
    average_score: Optional[float] = None
    average_completion_rate: Optional[float] = None
    average_satisfaction: Optional[float] = None
    average_time_spent: Optional[float] = None
    learners_by_profile: dict[str, int] = {}
    learners_in_difficulty: int = 0
    inactive_learners: int = 0
    advanced_learners: int = 0
    risk_indicators: dict[str, int] = {}
    score_histogram: list[ScoreBucket] = []
    performance_by_profile: list[ProfilePerformance] = []


class LearnerDashboard(BaseModel):
    learner: LearnerDetail
    stats_reference: dict[str, Any] = Field(
        default_factory=dict, description="Moyennes de la promotion, pour situer l'apprenant"
    )


class SystemEvent(BaseModel):
    type: str
    label: str
    learner: str
    learner_id: int
    created_at: dt.datetime


class HealthResponse(BaseModel):
    status: str
    database: dict[str, Any]
    models: dict[str, Any]
    tutor_engine: str
    version: str
