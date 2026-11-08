"""Schémas Pydantic pour les quiz et la bibliothèque de cours."""

from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIFFICULTIES = Literal["Facile", "Moyen", "Difficile"]
LEVELS = Literal["Débutant", "Intermédiaire", "Avancé"]


# --- Questions --------------------------------------------------------------


class QuestionInput(BaseModel):
    """Question créée par un formateur. `correct_index` reste côté serveur."""

    question_text: str = Field(..., min_length=5, max_length=1000)
    options: list[str] = Field(..., min_length=2, max_length=6)
    correct_index: int = Field(..., ge=0, le=5)
    points: float = Field(1.0, gt=0, le=100)
    concept: Optional[str] = Field(None, max_length=120)
    hint: Optional[str] = Field(None, max_length=1000)
    explanation: Optional[str] = Field(None, max_length=1000)

    @field_validator("options")
    @classmethod
    def _clean_options(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values]
        if any(not v for v in cleaned):
            raise ValueError("Aucune proposition de réponse ne peut être vide.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Deux propositions de réponse sont identiques.")
        return cleaned

    @model_validator(mode="after")
    def _check_correct_index(self):
        if self.correct_index >= len(self.options):
            raise ValueError(
                "L'index de la bonne réponse dépasse le nombre de propositions fournies."
            )
        # Un indice peut orienter le raisonnement, mais il ne doit pas contenir
        # textuellement la bonne proposition. Cette validation prévient les
        # fuites accidentelles lors de la création d'un quiz.
        if self.hint:
            hint = " ".join(self.hint.lower().split())
            answer = " ".join(self.options[self.correct_index].lower().split())
            if len(answer) >= 4 and answer in hint:
                raise ValueError("L'indice ne doit pas révéler textuellement la bonne réponse.")
        return self


class QuestionForLearner(BaseModel):
    """Question telle qu'elle est envoyée à l'apprenant : sans la bonne réponse."""

    id: int
    position: int
    question_text: str
    options: list[str]
    points: float


class QuestionFull(QuestionForLearner):
    """Question complète, réservée aux formateurs et administrateurs."""

    model_config = ConfigDict(from_attributes=True)

    correct_index: int
    concept: Optional[str] = None
    hint: Optional[str] = None
    explanation: Optional[str] = None


# --- Quiz -------------------------------------------------------------------


class QuizInput(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=60)
    passing_score: float = Field(50.0, ge=0, le=100)
    difficulty: DIFFICULTIES = "Moyen"
    is_published: bool = False
    course_resource_id: Optional[int] = Field(None, ge=1)
    questions: list[QuestionInput] = Field(..., min_length=1, max_length=50)


class QuizUpdate(BaseModel):
    """Mise à jour partielle. Fournir `questions` remplace toutes les questions."""

    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=60)
    passing_score: Optional[float] = Field(None, ge=0, le=100)
    difficulty: Optional[DIFFICULTIES] = None
    is_published: Optional[bool] = None
    course_resource_id: Optional[int] = Field(None, ge=1)
    questions: Optional[list[QuestionInput]] = Field(None, min_length=1, max_length=50)


class QuizSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: str
    passing_score: float
    is_published: bool
    course_resource_id: Optional[int] = None
    question_count: int = 0
    assigned_count: int = 0
    attempts_count: int = 0
    average_score: Optional[float] = None
    created_by: Optional[str] = None
    created_at: dt.datetime


class QuizFull(QuizSummary):
    questions: list[QuestionFull] = Field(default_factory=list)


class QuizForLearner(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: str
    passing_score: float
    course_resource_id: Optional[int] = None
    questions: list[QuestionForLearner]


class LearnerQuizCard(BaseModel):
    """Ligne de la liste « Mes quiz »."""

    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: str
    passing_score: float
    question_count: int
    assigned: bool
    due_date: Optional[dt.datetime] = None
    attempts_count: int
    best_score: Optional[float] = None
    passed: bool
    last_attempt_at: Optional[dt.datetime] = None


# --- Passage et correction --------------------------------------------------


class AnswerInput(BaseModel):
    question_id: int = Field(..., ge=1)
    chosen_index: Optional[int] = Field(None, ge=0, le=5)


class AttemptSubmit(BaseModel):
    """Copie envoyée par l'apprenant : uniquement des choix, jamais une note."""

    answers: list[AnswerInput] = Field(..., min_length=1, max_length=50)
    started_at: Optional[dt.datetime] = Field(
        None, description="Horodatage d'ouverture du quiz, pour mesurer la durée réelle"
    )

    @model_validator(mode="after")
    def _unique_questions(self):
        ids = [answer.question_id for answer in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Une question ne peut apparaître qu'une seule fois dans la copie.")
        return self


class AnswerResult(BaseModel):
    question_id: int
    question_text: str
    options: list[str]
    chosen_index: Optional[int] = None
    correct_index: int
    is_correct: bool
    points: float
    concept: Optional[str] = None
    explanation: Optional[str] = None


class AttemptResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    score: float
    correct_count: int
    total_questions: int
    passed: bool
    duration_seconds: int
    submitted_at: dt.datetime
    answers: list[AnswerResult] = Field(default_factory=list)


class AttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    quiz_title: Optional[str] = None
    score: float
    correct_count: int
    total_questions: int
    passed: bool
    duration_seconds: int
    submitted_at: dt.datetime


class TutorFeedback(BaseModel):
    """Coaching produit à partir des réponses réellement corrigées."""

    summary: str
    strengths: list[str] = Field(default_factory=list)
    focus_topics: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class AttemptWithProfile(BaseModel):
    """Résultat de correction + effet sur le profil, renvoyé après soumission."""

    attempt: AttemptResult
    previous_profile: Optional[str] = None
    new_profile: Optional[str] = None
    profile_changed: bool = False
    average_score: float
    completion_rate: float
    quiz_attempts: int
    tutor_feedback: TutorFeedback


class AttemptReview(AttemptResult):
    tutor_feedback: TutorFeedback


class HintResource(BaseModel):
    id: int
    title: str
    category: str
    level: str
    summary: Optional[str] = None


class QuizHintResponse(BaseModel):
    """Indice sûr : aucune bonne réponse ni explication de correction."""

    question_id: int
    hint: str
    concept: Optional[str] = None
    resources: list[HintResource] = Field(default_factory=list)


# --- Attribution ------------------------------------------------------------


class AssignInput(BaseModel):
    learner_ids: list[int] = Field(..., min_length=1, max_length=500)
    due_date: Optional[dt.datetime] = None


class AssignResult(BaseModel):
    assigned: int
    already_assigned: int
    updated_due_dates: int = 0
    unknown_learners: int


class QuizResultRow(BaseModel):
    learner_id: int
    student_id: str
    name: str
    assigned_at: Optional[dt.datetime] = None
    attempts: int
    best_score: Optional[float] = None
    passed: bool
    last_attempt_at: Optional[dt.datetime] = None


class QuestionStat(BaseModel):
    question_id: Optional[int] = None
    question_text: Optional[str] = None
    success_rate: Optional[float] = None
    answers: int


class QuizResults(BaseModel):
    quiz_id: int
    title: str
    passing_score: float
    assigned_count: int
    participants: int
    total_attempts: int
    average_score: Optional[float] = None
    pass_rate: Optional[float] = None
    rows: list[QuizResultRow]
    question_stats: list[QuestionStat]


class ManualEvaluationInput(BaseModel):
    """Note d'une évaluation hors ligne, saisie par un formateur."""

    score: float = Field(..., ge=0, le=100)
    title: Optional[str] = Field(None, max_length=200)
    duration_minutes: Optional[float] = Field(None, ge=0, le=1440)
    passing_score: float = Field(50.0, ge=0, le=100)


# --- Bibliothèque de cours --------------------------------------------------


class CourseInput(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    category: str = Field(..., min_length=2, max_length=60)
    summary: Optional[str] = Field(None, max_length=1000)
    content: str = Field(..., min_length=20, max_length=20000)
    keywords: Optional[str] = Field(None, max_length=500)
    level: LEVELS = "Débutant"


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    category: Optional[str] = Field(None, min_length=2, max_length=60)
    summary: Optional[str] = Field(None, max_length=1000)
    content: Optional[str] = Field(None, min_length=20, max_length=20000)
    keywords: Optional[str] = Field(None, max_length=500)
    level: Optional[LEVELS] = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    summary: Optional[str] = None
    content: str
    keywords: Optional[str] = None
    level: str
    created_at: dt.datetime
    updated_at: dt.datetime
    completed: bool = False
    completed_at: Optional[dt.datetime] = None
    recommended_quiz: Optional[LearnerQuizCard] = None


class CourseCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    summary: Optional[str] = None
    level: str
    updated_at: dt.datetime
    completed: bool = False
    completed_at: Optional[dt.datetime] = None
    recommended_quiz_id: Optional[int] = None


class CourseCompletionResponse(BaseModel):
    course_id: int
    completed_at: dt.datetime
    newly_completed: bool
    message: str
    recommended_quiz: Optional[LearnerQuizCard] = None


class CourseSearchHit(BaseModel):
    id: int
    title: str
    category: str
    level: str
    score: float
    passage: str
