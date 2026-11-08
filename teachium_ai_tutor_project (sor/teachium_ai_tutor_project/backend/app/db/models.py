"""Modèles ORM SQLAlchemy — schéma relationnel TEACHIUM AI Tutor (Neon PostgreSQL)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

ROLE_LEARNER = "learner"
ROLE_TRAINER = "trainer"
ROLE_ADMIN = "administrator"
ROLES = (ROLE_LEARNER, ROLE_TRAINER, ROLE_ADMIN)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    """Compte d'accès à la plateforme (apprenant, formateur ou administrateur)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_LEARNER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    learner: Mapped["Learner | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("role IN ('learner','trainer','administrator')", name="ck_users_role"),
    )

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return f"<User {self.email} ({self.role})>"


class Learner(Base):
    """Fiche apprenant : indicateurs pédagogiques utilisés par les modèles ML.

    `user_id` est optionnel : le dataset importé contient des apprenants
    anonymisés qui n'ont pas nécessairement de compte de connexion.
    """

    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    student_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    course_category: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)

    # Variables d'entrée des modèles (mêmes noms que dans le dataset CSV)
    average_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_spent_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quiz_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_quizzes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    login_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    satisfaction_score: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)

    completed_courses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_courses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Profil de référence fourni par le dataset simulé (cible d'entraînement).
    reference_profile: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(back_populates="learner")
    profiles: Mapped[list["LearnerProfile"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan", order_by="LearnerProfile.created_at.desc()"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan", order_by="Recommendation.created_at.desc()"
    )
    activities: Mapped[list["LearningActivity"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan", order_by="LearningActivity.created_at"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
    course_completions: Mapped[list["CourseCompletion"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan", order_by="CourseCompletion.completed_at"
    )

    __table_args__ = (
        CheckConstraint("average_score >= 0 AND average_score <= 100", name="ck_learners_score"),
        CheckConstraint("completion_rate >= 0 AND completion_rate <= 100", name="ck_learners_completion"),
        Index("ix_learners_score_completion", "average_score", "completion_rate"),
    )

    @property
    def display_name(self) -> str:
        if self.user is not None and self.user.name:
            return self.user.name
        return self.student_id

    def to_features(self) -> dict:
        """Dictionnaire au format attendu par les services ML existants."""
        return {
            "average_score": float(self.average_score),
            "time_spent_hours": float(self.time_spent_hours),
            "completion_rate": float(self.completion_rate),
            "quiz_attempts": int(self.quiz_attempts),
            "failed_quizzes": int(self.failed_quizzes),
            "login_frequency": int(self.login_frequency),
            "satisfaction_score": float(self.satisfaction_score),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Learner {self.student_id}>"


class LearnerProfile(Base):
    """Résultat horodaté d'une analyse de profil (Decision Tree + K-Means)."""

    __tablename__ = "learner_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    cluster: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'model' = arbre de décision entraîné, 'rules' = repli interprétable.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="model")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="profiles")

    __table_args__ = (Index("ix_learner_profiles_learner_created", "learner_id", "created_at"),)


class Recommendation(Base):
    """Ressource pédagogique proposée par le moteur de recommandation."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    profile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="recommendations")

    __table_args__ = (Index("ix_recommendations_learner_created", "learner_id", "created_at"),)


class LearningActivity(Base):
    """Trace d'activité d'apprentissage (quiz, cours, connexion...)."""

    __tablename__ = "learning_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="activities")

    __table_args__ = (Index("ix_activity_learner_created", "learner_id", "created_at"),)


class ChatMessage(Base):
    """Message échangé avec l'AI Tutor (historique de conversation)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="chat_messages")

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_chat_role"),
        Index("ix_chat_learner_created", "learner_id", "created_at"),
    )


# ============================================================================
#  Quiz : création par le formateur, passage et correction automatique
# ============================================================================


class Quiz(Base):
    """Quiz à choix multiples créé par un formateur ou un administrateur."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    # Note minimale, sur 100, pour considérer le quiz comme réussi.
    passing_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="Moyen")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Lien facultatif vers la fiche précisément évaluée. Les quiz historiques
    # restent compatibles : le moteur de recommandation utilise alors les
    # titres, mots-clés, descriptions et catégories.
    course_resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_resources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])
    course_resource: Mapped["CourseResource | None"] = relationship(
        foreign_keys=[course_resource_id]
    )
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.position"
    )
    assignments: Mapped[list["QuizAssignment"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("passing_score >= 0 AND passing_score <= 100", name="ck_quiz_passing_score"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Quiz {self.title!r}>"


class QuizQuestion(Base):
    """Question à choix unique. `options` contient la liste des propositions."""

    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Liste JSON des propositions, par exemple ["Réponse A", "Réponse B", ...].
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Index (base 0) de la bonne réponse dans `options`. Jamais envoyé à l'apprenant
    # avant la correction.
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # Notion pédagogique ciblée. Elle permet au tuteur de regrouper les erreurs
    # et de recommander la bonne fiche de cours après une tentative.
    concept: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # Indice progressif, volontairement distinct de l'explication de correction.
    # Il peut être montré avant la soumission et ne doit jamais révéler la réponse.
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")

    __table_args__ = (
        CheckConstraint("correct_index >= 0", name="ck_question_correct_index"),
        CheckConstraint("points > 0", name="ck_question_points"),
        Index("ix_questions_quiz_position", "quiz_id", "position"),
    )


class QuizAssignment(Base):
    """Attribution d'un quiz à un apprenant par un formateur."""

    __tablename__ = "quiz_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="assignments")
    learner: Mapped["Learner"] = relationship()
    assigned_by: Mapped["User | None"] = relationship(foreign_keys=[assigned_by_id])

    __table_args__ = (
        UniqueConstraint("quiz_id", "learner_id", name="uq_assignment_quiz_learner"),
    )


class QuizAttempt(Base):
    """Passage d'un quiz par un apprenant, corrigé côté serveur.

    `answers` conserve le détail : pour chaque question, la réponse choisie,
    la bonne réponse et le résultat. La note n'est jamais fournie par
    l'apprenant : elle est calculée par `quiz_service.grade_attempt()`.
    """

    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")
    learner: Mapped["Learner"] = relationship()

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_attempt_score"),
        Index("ix_attempts_learner_submitted", "learner_id", "submitted_at"),
    )


class CourseResource(Base):
    """Fiche de cours consultable par les apprenants et utilisée par l'AI Tutor.

    L'AI Tutor recherche dans ces fiches par similarité TF-IDF pour répondre
    aux questions portant sur le contenu des cours.
    """

    __tablename__ = "course_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Mots-clés séparés par des virgules, pondérés dans la recherche.
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="Débutant")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])
    completions: Mapped[list["CourseCompletion"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_course_category_level", "category", "level"),)

    def searchable_text(self) -> str:
        """Texte concaténé utilisé pour l'indexation TF-IDF."""
        parts = [self.title, self.title, self.category, self.keywords or "", self.summary or "", self.content]
        return " ".join(p for p in parts if p)


class CourseCompletion(Base):
    """Confirmation idempotente qu'un apprenant a terminé une fiche de cours.

    Le quiz recommandé est mémorisé afin qu'un second clic sur le bouton de
    confirmation renvoie la même proposition au lieu d'en choisir une autre.
    """

    __tablename__ = "course_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course_resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommended_quiz_id: Mapped[int | None] = mapped_column(
        ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="course_completions")
    course: Mapped["CourseResource"] = relationship(back_populates="completions")
    recommended_quiz: Mapped["Quiz | None"] = relationship(foreign_keys=[recommended_quiz_id])

    __table_args__ = (
        UniqueConstraint("learner_id", "course_id", name="uq_course_completion_learner_course"),
        Index("ix_course_completions_learner_completed", "learner_id", "completed_at"),
    )
