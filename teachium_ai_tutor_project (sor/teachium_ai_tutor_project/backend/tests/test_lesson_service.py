"""Tests locaux du parcours cours terminé -> quiz recommandé.

Ils utilisent SQLite en mémoire : aucune connexion Neon n'est nécessaire.
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import (
    CourseCompletion,
    CourseResource,
    Learner,
    LearningActivity,
    Quiz,
    QuizAssignment,
    QuizQuestion,
)
from app.services import lesson_service, quiz_service


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _quiz(
    db: Session,
    title: str,
    category: str,
    question: str,
    *,
    course_id: int | None = None,
) -> Quiz:
    quiz = Quiz(
        title=title,
        description=f"Évaluation sur {title}",
        category=category,
        difficulty="Facile",
        passing_score=50,
        is_published=True,
        course_resource_id=course_id,
    )
    db.add(quiz)
    db.flush()
    db.add(
        QuizQuestion(
            quiz_id=quiz.id,
            position=0,
            question_text=question,
            options=["Oui", "Non"],
            correct_index=0,
            points=1,
        )
    )
    db.flush()
    db.refresh(quiz)
    return quiz


def test_completion_is_isolated_idempotent_and_assigns_exact_quiz():
    db = _session()
    try:
        learner = Learner(student_id="TEST-LESSON-1", course_category="Python")
        other_learner = Learner(student_id="TEST-LESSON-2", course_category="Python")
        course = CourseResource(
            title="Les boucles Python",
            category="Python",
            summary="Comprendre les répétitions.",
            content="Les boucles for et while permettent de répéter des instructions.",
            keywords="for, while, itération",
            level="Débutant",
        )
        db.add_all([learner, other_learner, course])
        db.flush()

        fallback = _quiz(db, "Variables Python", "Python", "Une variable stocke-t-elle une valeur ?")
        exact = _quiz(
            db,
            "Contrôle des boucles",
            "Python",
            "Une boucle sert-elle à répéter une instruction ?",
            course_id=course.id,
        )
        db.commit()

        first = lesson_service.complete_course(db, learner, course)
        second = lesson_service.complete_course(db, learner, course)

        assert first["newly_completed"] is True
        assert second["newly_completed"] is False
        assert first["completed_at"] == second["completed_at"]
        assert first["recommended_quiz"]["id"] == exact.id
        assert second["recommended_quiz"]["id"] == exact.id
        assert second["recommended_quiz"]["assigned"] is True

        assignments = db.scalar(
            select(func.count(QuizAssignment.id)).where(
                QuizAssignment.learner_id == learner.id,
                QuizAssignment.quiz_id == exact.id,
            )
        )
        activities = db.scalar(
            select(func.count(LearningActivity.id)).where(
                LearningActivity.learner_id == learner.id,
                LearningActivity.activity_type == "course_completed",
            )
        )
        assert assignments == 1
        assert activities == 1
        assert lesson_service.completion_map(db, other_learner.id) == {}
        assert any(card["id"] == exact.id for card in quiz_service.available_quizzes(db, learner))

        # Une proposition supprimée ou dépubliée est revalidée, sans recréer
        # l'événement de fin de cours.
        exact.is_published = False
        db.commit()
        refreshed = lesson_service.complete_course(db, learner, course)
        assert refreshed["newly_completed"] is False
        assert refreshed["recommended_quiz"]["id"] == fallback.id
        assert db.scalar(
            select(func.count(LearningActivity.id)).where(
                LearningActivity.learner_id == learner.id,
                LearningActivity.activity_type == "course_completed",
            )
        ) == 1
    finally:
        db.close()


def test_fallback_prefers_title_keywords_and_question_concepts():
    db = _session()
    try:
        learner = Learner(student_id="TEST-FALLBACK", course_category="Data")
        course = CourseResource(
            title="Normalisation avant K-Means",
            category="Data",
            summary="Mettre les variables à la même échelle avant le clustering.",
            content="StandardScaler évite qu'une variable domine le calcul des distances.",
            keywords="normalisation, standardisation, distance, clustering",
            level="Intermédiaire",
        )
        db.add_all([learner, course])
        db.flush()
        unrelated = _quiz(db, "Valeurs manquantes", "Data", "Que signifie une valeur nulle ?")
        relevant = _quiz(
            db,
            "K-Means et normalisation",
            "Data",
            "Pourquoi standardiser avant un clustering par distance ?",
        )
        db.commit()

        result = lesson_service.complete_course(db, learner, course)
        assert result["recommended_quiz"]["id"] == relevant.id
        assert result["recommended_quiz"]["id"] != unrelated.id
    finally:
        db.close()


def test_completion_succeeds_when_no_published_quiz_matches():
    db = _session()
    try:
        learner = Learner(student_id="TEST-NONE", course_category="Management")
        course = CourseResource(
            title="Conduite du changement",
            category="Management",
            content="Préparer les équipes et accompagner une transformation durable.",
            keywords="changement, équipe",
            level="Avancé",
        )
        db.add_all([learner, course])
        db.flush()
        _quiz(db, "Syntaxe Python", "Python", "Comment déclarer une fonction ?")
        db.commit()

        first = lesson_service.complete_course(db, learner, course)
        second = lesson_service.complete_course(db, learner, course)
        assert first["newly_completed"] is True
        assert second["newly_completed"] is False
        assert first["recommended_quiz"] is None
        assert second["recommended_quiz"] is None
        assert db.scalar(select(func.count(CourseCompletion.id))) == 1
        assert db.scalar(select(func.count(LearningActivity.id))) == 1
    finally:
        db.close()
