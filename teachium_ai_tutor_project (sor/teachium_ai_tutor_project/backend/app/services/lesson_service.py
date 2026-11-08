"""Progression dans les cours et recommandation d'un quiz existant.

Le service n'invente aucun contenu. Il choisit uniquement parmi les quiz déjà
publiés, en privilégiant un lien explicite avec la fiche puis une similarité
sur la filière, le titre, les mots-clés et les notions des questions.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CourseCompletion,
    CourseResource,
    Learner,
    LearningActivity,
    Quiz,
    QuizAssignment,
    QuizAttempt,
)
from app.services import quiz_service


_TOKEN_RE = re.compile(r"[a-z0-9+#]+")
_STOP_WORDS = {
    "a", "afin", "au", "aux", "avec", "ce", "ces", "cette", "dans", "de", "des",
    "du", "en", "et", "est", "la", "le", "les", "leur", "leurs", "on", "ou", "par",
    "pour", "qu", "que", "qui", "sur", "un", "une", "vos", "votre", "the", "and",
    "of", "to", "in", "for", "with", "is", "quiz", "cours", "introduction", "bases",
}


def _tokens(value: str | None) -> set[str]:
    """Normalise accents et casse pour comparer les métadonnées pédagogiques."""
    if not value:
        return set()
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    return {
        token
        for token in _TOKEN_RE.findall(ascii_value)
        if len(token) > 1 and token not in _STOP_WORDS
    }


def completion_map(
    db: Session, learner_id: int, course_ids: list[int] | None = None
) -> dict[int, CourseCompletion]:
    """Renvoie les confirmations d'un apprenant, indexées par fiche."""
    stmt = select(CourseCompletion).where(CourseCompletion.learner_id == learner_id)
    if course_ids is not None:
        if not course_ids:
            return {}
        stmt = stmt.where(CourseCompletion.course_id.in_(course_ids))
    rows = db.execute(stmt).scalars()
    return {row.course_id: row for row in rows}


def _semantic_score(course: CourseResource, quiz: Quiz) -> int:
    course_title = _tokens(course.title)
    course_keywords = _tokens(course.keywords)
    course_summary = _tokens(course.summary)

    quiz_title = _tokens(quiz.title)
    quiz_description = _tokens(quiz.description)
    quiz_questions: set[str] = set()
    for question in quiz.questions:
        quiz_questions |= _tokens(question.question_text)
        quiz_questions |= _tokens(question.concept)

    quiz_all = quiz_title | quiz_description | quiz_questions
    score = 0
    if _tokens(course.category) == _tokens(quiz.category):
        score += 40
    score += 14 * len(course_title & quiz_title)
    score += 7 * len(course_keywords & (quiz_title | quiz_description))
    score += 4 * len(course_title & (quiz_description | quiz_questions))
    score += 2 * len((course_keywords | course_summary) & quiz_all)
    return score


def recommend_quiz(db: Session, learner: Learner, course: CourseResource) -> Quiz | None:
    """Choisit le quiz publié le plus pertinent sans ajouter de contenu.

    Un lien explicite ``course_resource_id`` est prioritaire. Pour les données
    historiques dépourvues de lien, la filière délimite le choix et les termes
    pédagogiques départagent les quiz. À pertinence égale, un quiz non réussi
    et moins souvent tenté est proposé en premier.
    """
    quizzes = list(
        db.execute(
            select(Quiz)
            .options(selectinload(Quiz.questions))
            .where(Quiz.is_published.is_(True))
            .order_by(Quiz.id)
        ).scalars()
    )
    quizzes = [quiz for quiz in quizzes if quiz.questions]
    if not quizzes:
        return None

    exact = [quiz for quiz in quizzes if quiz.course_resource_id == course.id]
    if exact:
        candidates = exact
    else:
        course_category = _tokens(course.category)
        same_category = [
            quiz for quiz in quizzes if course_category and _tokens(quiz.category) == course_category
        ]
        if same_category:
            candidates = same_category
        else:
            # Dernier recours : un recouvrement sémantique significatif. On ne
            # propose jamais arbitrairement un quiz d'une autre matière.
            candidates = [quiz for quiz in quizzes if _semantic_score(course, quiz) >= 14]

    if not candidates:
        return None

    attempt_rows = db.execute(
        select(QuizAttempt.quiz_id, QuizAttempt.passed).where(
            QuizAttempt.learner_id == learner.id,
            QuizAttempt.quiz_id.in_([quiz.id for quiz in candidates]),
        )
    ).all()
    attempt_counts: dict[int, int] = {}
    passed_ids: set[int] = set()
    for quiz_id, passed in attempt_rows:
        attempt_counts[quiz_id] = attempt_counts.get(quiz_id, 0) + 1
        if passed:
            passed_ids.add(quiz_id)

    candidates.sort(
        key=lambda quiz: (
            quiz.id in passed_ids,
            -_semantic_score(course, quiz),
            attempt_counts.get(quiz.id, 0),
            quiz.id,
        )
    )
    return candidates[0]


def complete_course(db: Session, learner: Learner, course: CourseResource) -> dict:
    """Confirme la lecture et attribue une proposition, de façon rejouable."""
    completion = db.execute(
        select(CourseCompletion).where(
            CourseCompletion.learner_id == learner.id,
            CourseCompletion.course_id == course.id,
        )
    ).scalar_one_or_none()
    newly_completed = completion is None

    if completion is None:
        try:
            # Le SAVEPOINT rend un double clic réellement idempotent, même si
            # deux requêtes arrivent simultanément sur Neon.
            with db.begin_nested():
                completion = CourseCompletion(learner_id=learner.id, course_id=course.id)
                db.add(completion)
                db.flush()
        except IntegrityError:
            completion = db.execute(
                select(CourseCompletion).where(
                    CourseCompletion.learner_id == learner.id,
                    CourseCompletion.course_id == course.id,
                )
            ).scalar_one()
            newly_completed = False

        if newly_completed:
            db.add(
                LearningActivity(
                    learner_id=learner.id,
                    activity_type="course_completed",
                    title=course.title,
                )
            )

    quiz = None
    if completion.recommended_quiz_id is not None:
        saved_quiz = db.get(Quiz, completion.recommended_quiz_id)
        if saved_quiz is not None and saved_quiz.is_published and saved_quiz.questions:
            quiz = saved_quiz

    if quiz is None:
        quiz = recommend_quiz(db, learner, course)
        completion.recommended_quiz_id = quiz.id if quiz is not None else None

    if quiz is not None:
        assignment = db.execute(
            select(QuizAssignment).where(
                QuizAssignment.quiz_id == quiz.id,
                QuizAssignment.learner_id == learner.id,
            )
        ).scalar_one_or_none()
        if assignment is None:
            try:
                with db.begin_nested():
                    db.add(
                        QuizAssignment(
                            quiz_id=quiz.id,
                            learner_id=learner.id,
                            # Attribution déclenchée par l'apprenant après lecture :
                            # aucun formateur n'est faussement crédité.
                            assigned_by_id=None,
                        )
                    )
                    db.flush()
            except IntegrityError:
                # Une requête jumelle vient d'effectuer exactement la même
                # attribution ; l'état final attendu est déjà atteint.
                pass

    db.commit()
    db.refresh(completion)

    quiz_card = None
    if quiz is not None:
        quiz_card = next(
            (item for item in quiz_service.available_quizzes(db, learner) if item["id"] == quiz.id),
            None,
        )

    return {
        "course_id": course.id,
        "completed_at": completion.completed_at,
        "newly_completed": newly_completed,
        "message": (
            "Cours marqué comme terminé. Un quiz adapté est prêt."
            if quiz_card is not None
            else "Cours marqué comme terminé. Aucun quiz publié correspondant n'est encore disponible."
        ),
        "recommended_quiz": quiz_card,
    }
