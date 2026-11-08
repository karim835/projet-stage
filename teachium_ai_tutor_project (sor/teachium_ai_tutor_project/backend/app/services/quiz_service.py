"""Service des quiz : création, attribution, correction automatique.

Principe de conception essentiel
--------------------------------
**Un apprenant ne saisit jamais sa propre note.** Il choisit uniquement des
réponses ; la correction, le calcul de la note et la mise à jour des indicateurs
sont effectués côté serveur par ce module. La bonne réponse (`correct_index`)
n'est jamais transmise à l'apprenant avant la soumission de sa copie.

Deux sources de notes existent, toutes deux contrôlées par le serveur :

1. **Quiz passé dans l'application** — corrigé automatiquement ici ;
2. **Évaluation hors ligne** — note saisie par un *formateur* (devoir, examen
   en présentiel), enregistrée via `record_manual_evaluation()`.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Learner,
    LearningActivity,
    Quiz,
    QuizAssignment,
    QuizAttempt,
    QuizQuestion,
)
from app.services import tutor_service


class QuizError(Exception):
    """Erreur métier liée aux quiz (message destiné à l'utilisateur)."""


# --- Lecture ----------------------------------------------------------------


def get_quiz(db: Session, quiz_id: int, with_questions: bool = True) -> Quiz | None:
    stmt = select(Quiz).where(Quiz.id == quiz_id)
    if with_questions:
        stmt = stmt.options(selectinload(Quiz.questions))
    return db.execute(stmt).scalar_one_or_none()


def available_quizzes(db: Session, learner: Learner) -> list[dict]:
    """Quiz visibles par un apprenant : ceux qui lui sont attribués + les quiz
    publiés de sa filière. Les questions ne sont pas incluses ici."""
    assignments = dict(
        db.execute(
            select(QuizAssignment.quiz_id, QuizAssignment.due_date).where(
                QuizAssignment.learner_id == learner.id
            )
        ).all()
    )

    stmt = select(Quiz).where(Quiz.is_published.is_(True))
    quizzes = list(db.execute(stmt.order_by(Quiz.created_at.desc())).scalars())

    # Statistiques de passage de cet apprenant, quiz par quiz.
    attempts = list(
        db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.learner_id == learner.id)
            .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())
        ).scalars()
    )
    by_quiz: dict[int, list[QuizAttempt]] = {}
    for attempt in attempts:
        by_quiz.setdefault(attempt.quiz_id, []).append(attempt)

    question_counts = dict(
        db.execute(
            select(QuizQuestion.quiz_id, func.count(QuizQuestion.id)).group_by(QuizQuestion.quiz_id)
        ).all()
    )

    result = []
    for quiz in quizzes:
        is_assigned = quiz.id in assignments
        same_category = (
            learner.course_category is not None
            and quiz.category is not None
            and quiz.category == learner.course_category
        )
        if not (is_assigned or same_category):
            continue

        quiz_attempts = by_quiz.get(quiz.id, [])
        best = max((a.score for a in quiz_attempts), default=None)
        result.append(
            {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "category": quiz.category,
                "difficulty": quiz.difficulty,
                "passing_score": quiz.passing_score,
                "question_count": int(question_counts.get(quiz.id, 0)),
                "assigned": is_assigned,
                "due_date": assignments.get(quiz.id),
                "attempts_count": len(quiz_attempts),
                "best_score": best,
                "passed": any(a.passed for a in quiz_attempts),
                "last_attempt_at": quiz_attempts[0].submitted_at if quiz_attempts else None,
            }
        )
    # À faire d'abord, puis échéance la plus proche, puis nouveautés.
    far_future = dt.datetime.max.replace(tzinfo=dt.timezone.utc)

    def due_key(value: dt.datetime | None) -> dt.datetime:
        if value is None:
            return far_future
        return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)

    result.sort(
        key=lambda item: (
            item["passed"],
            due_key(item["due_date"]),
            -item["id"],
        )
    )
    return result


def quiz_for_taking(db: Session, quiz: Quiz) -> dict:
    """Version du quiz envoyée à l'apprenant : **sans les bonnes réponses**."""
    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "category": quiz.category,
        "difficulty": quiz.difficulty,
        "passing_score": quiz.passing_score,
        "course_resource_id": quiz.course_resource_id,
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "question_text": q.question_text,
                "options": list(q.options or []),
                "points": q.points,
            }
            for q in sorted(quiz.questions, key=lambda q: (q.position, q.id))
        ],
    }


def question_hint(db: Session, quiz: Quiz, question_id: int) -> dict:
    """Construit un indice pédagogique sans exposer la correction.

    Un indice rédigé par le formateur est prioritaire. Sinon, le service donne
    une stratégie de raisonnement générique et cherche jusqu'à deux fiches de
    cours pertinentes. Ni ``correct_index`` ni ``explanation`` ne quittent ce
    service avant la soumission de la copie.
    """
    question = next((item for item in quiz.questions if item.id == question_id), None)
    if question is None:
        raise QuizError("Cette question n'appartient pas au quiz.")

    concept = (question.concept or "").strip() or None
    hint = (question.hint or "").strip()
    if not hint:
        focus = concept or quiz.category or "la notion centrale"
        hint = (
            f"Concentrez-vous sur {focus}. Reformulez l'énoncé avec vos propres mots, "
            "puis éliminez les propositions qui contredisent la définition ou la règle du cours."
        )

    resources: list[dict] = []
    try:
        from app.services import knowledge_service

        query = " ".join(part for part in [concept, quiz.category, question.question_text] if part)
        for hit in knowledge_service.search(db, query, top_k=2, category=quiz.category):
            resource = hit["resource"]
            resources.append(
                {
                    "id": resource.id,
                    "title": resource.title,
                    "category": resource.category,
                    "level": resource.level,
                    "summary": resource.summary,
                }
            )
    except (LookupError, ValueError):
        # L'indice rédigé reste disponible même si l'index documentaire est
        # momentanément vide ou qu'une requête ne contient aucun terme utile.
        resources = []

    return {
        "question_id": question.id,
        "hint": hint,
        "concept": concept,
        "resources": resources,
    }


# --- Correction -------------------------------------------------------------


def grade_attempt(
    db: Session,
    learner: Learner,
    quiz: Quiz,
    answers: dict[int, int | None],
    started_at: dt.datetime | None = None,
) -> QuizAttempt:
    """Corrige une copie et enregistre le passage.

    `answers` associe un identifiant de question à l'index choisi (ou None si
    la question a été laissée sans réponse).
    """
    questions = sorted(quiz.questions, key=lambda q: (q.position, q.id))
    if not questions:
        raise QuizError("Ce quiz ne contient aucune question : il ne peut pas être passé.")

    total_points = sum(float(q.points) for q in questions)
    earned = 0.0
    detail = []
    correct_count = 0

    for question in questions:
        chosen = answers.get(question.id)
        if chosen is not None:
            try:
                chosen = int(chosen)
            except (TypeError, ValueError):
                chosen = None
        options = list(question.options or [])
        if chosen is not None and not (0 <= chosen < len(options)):
            chosen = None  # index hors bornes : traité comme sans réponse

        is_correct = chosen is not None and chosen == question.correct_index
        if is_correct:
            earned += float(question.points)
            correct_count += 1

        detail.append(
            {
                "question_id": question.id,
                "question_text": question.question_text,
                "options": options,
                "chosen_index": chosen,
                "correct_index": question.correct_index,
                "is_correct": is_correct,
                "points": float(question.points),
                "concept": question.concept,
                "explanation": question.explanation,
            }
        )

    score = round((earned / total_points) * 100.0, 2) if total_points > 0 else 0.0
    now = dt.datetime.now(dt.timezone.utc)

    duration = 0
    if started_at is not None:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=dt.timezone.utc)
        # Borne haute : une copie ouverte puis oubliée ne doit pas ajouter des
        # heures fictives au temps d'apprentissage.
        duration = max(0, min(int((now - started_at).total_seconds()), 4 * 3600))

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        learner_id=learner.id,
        score=score,
        correct_count=correct_count,
        total_questions=len(questions),
        passed=score >= float(quiz.passing_score),
        duration_seconds=duration,
        answers=detail,
        started_at=started_at,
        submitted_at=now,
    )
    db.add(attempt)
    db.flush()

    _apply_attempt_to_metrics(db, learner, quiz, attempt)

    db.add(
        LearningActivity(
            learner_id=learner.id,
            activity_type="quiz",
            title=quiz.title,
            score=score,
            duration_minutes=round(duration / 60.0, 2) if duration else None,
            created_at=now,
        )
    )
    db.commit()
    db.refresh(attempt)
    db.refresh(learner)

    # Le profil et les recommandations sont recalculés à partir des nouveaux
    # indicateurs : c'est la note corrigée par le serveur qui alimente les modèles.
    tutor_service.run_analysis(db, learner)
    db.refresh(learner)
    return attempt


def _apply_attempt_to_metrics(db: Session, learner: Learner, quiz: Quiz, attempt: QuizAttempt) -> None:
    """Répercute une copie corrigée sur les indicateurs de l'apprenant."""
    previous_attempts = max(int(learner.quiz_attempts), 0)

    # Moyenne incrémentale : la moyenne importée est considérée comme la moyenne
    # des `quiz_attempts` évaluations déjà réalisées.
    new_average = (float(learner.average_score) * previous_attempts + attempt.score) / (previous_attempts + 1)
    learner.average_score = round(min(max(new_average, 0.0), 100.0), 2)
    learner.quiz_attempts = previous_attempts + 1
    if not attempt.passed:
        learner.failed_quizzes = int(learner.failed_quizzes) + 1

    if attempt.duration_seconds:
        learner.time_spent_hours = round(
            float(learner.time_spent_hours) + attempt.duration_seconds / 3600.0, 2
        )

    # Un quiz est une évaluation, pas un cours. Il met à jour la moyenne et les
    # compteurs de quiz, mais ne doit jamais modifier artificiellement le taux
    # de complétion des cours importé depuis le LMS.


def _unique_text(values: list[str | None], limit: int = 5) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = (raw or "").strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def tutor_feedback(db: Session, quiz: Quiz, attempt: QuizAttempt) -> dict:
    """Retour pédagogique personnalisé construit à partir de la copie corrigée."""
    items = list(attempt.answers or [])
    correct = [item for item in items if item.get("is_correct")]
    wrong = [item for item in items if not item.get("is_correct")]

    strengths = _unique_text(
        [item.get("concept") for item in correct], limit=4
    )
    focus_topics = _unique_text(
        [item.get("concept") or item.get("question_text") for item in wrong], limit=5
    )

    if attempt.score >= 85:
        summary = (
            f"Très bonne maîtrise : {attempt.correct_count}/{attempt.total_questions} réponses correctes "
            f"et {attempt.score:.0f}/100. Consolidez les rares points hésitants, puis passez au niveau suivant."
        )
    elif attempt.passed:
        summary = (
            f"Objectif atteint avec {attempt.score:.0f}/100. Vous maîtrisez l'essentiel ; "
            "une révision ciblée des erreurs rendra ces acquis plus solides."
        )
    else:
        summary = (
            f"Vous obtenez {attempt.score:.0f}/100. Ce résultat sert de diagnostic : "
            "reprenez les notions ciblées ci-dessous avant une nouvelle tentative."
        )

    next_steps: list[str] = []
    if focus_topics:
        try:
            from app.services import knowledge_service

            for topic in focus_topics[:3]:
                hits = knowledge_service.search(db, topic, top_k=1, category=quiz.category)
                if hits:
                    resource = hits[0]["resource"]
                    if topic.rstrip().endswith(("?", ":")):
                        step = f"Relire « {resource.title} » pour reprendre la question « {topic.rstrip()} »."
                    else:
                        step = f"Relire « {resource.title} », en particulier la notion « {topic} »."
                else:
                    if topic.rstrip().endswith(("?", ":")):
                        step = f"Reprendre la question « {topic.rstrip()} » dans vos supports de cours."
                    else:
                        step = f"Revoir la notion « {topic} » dans vos supports de cours."
                if step not in next_steps:
                    next_steps.append(step)
        except (LookupError, ValueError):
            next_steps = [f"Revoir la notion « {topic} »." for topic in focus_topics[:3]]
        next_steps.append("Refaire le quiz après une courte pause, sans consulter la correction.")
    else:
        next_steps = [
            "Passez à un quiz de difficulté supérieure dans la même filière.",
            "Expliquez une notion du quiz avec vos propres mots pour consolider l'acquis.",
        ]

    suggested_questions: list[str] = []
    if wrong:
        first_error = wrong[0]
        concept = (first_error.get("concept") or "").strip()
        question = (first_error.get("question_text") or "").strip()
        if concept:
            suggested_questions.extend(
                [
                    f"Peux-tu m'expliquer simplement la notion « {concept} » ?",
                    f"Peux-tu me donner un exemple guidé pour comprendre « {concept} » ?",
                ]
            )
        elif question:
            suggested_questions.extend(
                [
                    f"Peux-tu m'aider à comprendre mon erreur sur cette question : « {question} » ?",
                    f"Quelle règle du cours dois-je retenir pour répondre correctement à « {question} » ?",
                ]
            )
        suggested_questions.append(
            f"Analyse mes erreurs au quiz « {quiz.title} » sans me donner directement les réponses."
        )

    return {
        "summary": summary,
        "strengths": strengths,
        "focus_topics": focus_topics,
        "next_steps": next_steps,
        "suggested_questions": suggested_questions,
    }


def record_manual_evaluation(
    db: Session,
    learner: Learner,
    score: float,
    title: str | None = None,
    duration_minutes: float | None = None,
    passing_score: float = 50.0,
) -> LearningActivity:
    """Note d'une évaluation hors ligne, saisie **par un formateur**.

    Utilisé pour les devoirs et examens qui n'ont pas lieu dans l'application.
    L'apprenant n'a pas accès à cette opération.
    """
    score = float(score)
    if not 0 <= score <= 100:
        raise QuizError("La note doit être comprise entre 0 et 100.")

    previous_attempts = max(int(learner.quiz_attempts), 0)
    new_average = (float(learner.average_score) * previous_attempts + score) / (previous_attempts + 1)
    learner.average_score = round(min(max(new_average, 0.0), 100.0), 2)
    learner.quiz_attempts = previous_attempts + 1
    if score < passing_score:
        learner.failed_quizzes = int(learner.failed_quizzes) + 1
    if duration_minutes:
        learner.time_spent_hours = round(float(learner.time_spent_hours) + duration_minutes / 60.0, 2)

    activity = LearningActivity(
        learner_id=learner.id,
        activity_type="evaluation",
        title=(title or "").strip() or "Évaluation saisie par le formateur",
        score=score,
        duration_minutes=duration_minutes,
    )
    db.add(activity)
    db.commit()
    db.refresh(learner)
    db.refresh(activity)

    tutor_service.run_analysis(db, learner)
    db.refresh(learner)
    return activity


# --- Attribution ------------------------------------------------------------


def assign_quiz(
    db: Session,
    quiz: Quiz,
    learner_ids: list[int],
    assigned_by_id: int | None,
    due_date: dt.datetime | None = None,
) -> dict:
    """Attribue un quiz à plusieurs apprenants. Sans doublon, rejouable."""
    existing_rows = list(
        db.execute(
            select(QuizAssignment).where(QuizAssignment.quiz_id == quiz.id)
        ).scalars()
    )
    existing = {assignment.learner_id: assignment for assignment in existing_rows}
    valid_ids = set(
        db.execute(select(Learner.id).where(Learner.id.in_(learner_ids))).scalars()
    )

    created = 0
    updated_due_dates = 0
    for learner_id in valid_ids:
        if learner_id in existing:
            assignment = existing[learner_id]
            if due_date is not None and assignment.due_date != due_date:
                assignment.due_date = due_date
                updated_due_dates += 1
            continue
        db.add(
            QuizAssignment(
                quiz_id=quiz.id,
                learner_id=learner_id,
                assigned_by_id=assigned_by_id,
                due_date=due_date,
            )
        )
        created += 1

    db.commit()
    return {
        "assigned": created,
        "already_assigned": len(valid_ids & set(existing)),
        "updated_due_dates": updated_due_dates,
        "unknown_learners": len(set(learner_ids) - valid_ids),
    }


def unassign_quiz(db: Session, quiz: Quiz, learner_id: int) -> bool:
    assignment = db.execute(
        select(QuizAssignment).where(
            QuizAssignment.quiz_id == quiz.id, QuizAssignment.learner_id == learner_id
        )
    ).scalar_one_or_none()
    if assignment is None:
        return False

    db.delete(assignment)
    db.commit()
    return True


# --- Résultats --------------------------------------------------------------


def quiz_results(db: Session, quiz: Quiz) -> dict:
    """Synthèse des résultats d'un quiz, pour le formateur."""
    attempts = list(
        db.execute(
            select(QuizAttempt, Learner)
            .join(Learner, Learner.id == QuizAttempt.learner_id)
            .options(selectinload(QuizAttempt.learner).selectinload(Learner.user))
            .where(QuizAttempt.quiz_id == quiz.id)
            .order_by(QuizAttempt.submitted_at.desc())
        ).all()
    )

    assignments = list(
        db.execute(
            select(QuizAssignment, Learner)
            .join(Learner, Learner.id == QuizAssignment.learner_id)
            .options(selectinload(QuizAssignment.learner).selectinload(Learner.user))
            .where(QuizAssignment.quiz_id == quiz.id)
            .order_by(Learner.student_id)
        ).all()
    )

    best_by_learner: dict[int, QuizAttempt] = {}
    latest_by_learner: dict[int, QuizAttempt] = {}
    for attempt, _ in attempts:
        latest_by_learner.setdefault(attempt.learner_id, attempt)
        current = best_by_learner.get(attempt.learner_id)
        if current is None or attempt.score > current.score:
            best_by_learner[attempt.learner_id] = attempt

    scores = [a.score for a in best_by_learner.values()]
    passed = sum(1 for a in best_by_learner.values() if a.passed)

    rows = []
    for assignment, learner in assignments:
        best = best_by_learner.get(learner.id)
        rows.append(
            {
                "learner_id": learner.id,
                "student_id": learner.student_id,
                "name": learner.display_name,
                "assigned_at": assignment.created_at,
                "attempts": sum(1 for a, _ in attempts if a.learner_id == learner.id),
                "best_score": best.score if best else None,
                "passed": bool(best.passed) if best else False,
                "last_attempt_at": latest_by_learner[learner.id].submitted_at if learner.id in latest_by_learner else None,
            }
        )

    # Apprenants ayant passé le quiz sans y être formellement attribué
    # (quiz publié dans leur filière).
    assigned_ids = {learner.id for _, learner in assignments}
    for attempt, learner in attempts:
        if learner.id in assigned_ids:
            continue
        assigned_ids.add(learner.id)
        best = best_by_learner.get(learner.id)
        rows.append(
            {
                "learner_id": learner.id,
                "student_id": learner.student_id,
                "name": learner.display_name,
                "assigned_at": None,
                "attempts": sum(1 for a, _ in attempts if a.learner_id == learner.id),
                "best_score": best.score if best else None,
                "passed": bool(best.passed) if best else False,
                "last_attempt_at": latest_by_learner[learner.id].submitted_at if learner.id in latest_by_learner else None,
            }
        )

    # Taux de réussite question par question, utile pour repérer les notions
    # mal comprises par le groupe.
    per_question: dict[int, dict] = {}
    for attempt, _ in attempts:
        for item in attempt.answers or []:
            entry = per_question.setdefault(
                item.get("question_id"),
                {"question_text": item.get("question_text"), "correct": 0, "total": 0},
            )
            entry["total"] += 1
            if item.get("is_correct"):
                entry["correct"] += 1

    question_stats = [
        {
            "question_id": qid,
            "question_text": data["question_text"],
            "success_rate": round(data["correct"] / data["total"] * 100, 1) if data["total"] else None,
            "answers": data["total"],
        }
        for qid, data in per_question.items()
    ]
    question_stats.sort(key=lambda q: (q["success_rate"] if q["success_rate"] is not None else 999))

    return {
        "quiz_id": quiz.id,
        "title": quiz.title,
        "passing_score": quiz.passing_score,
        "assigned_count": len(assignments),
        "participants": len(best_by_learner),
        "total_attempts": len(attempts),
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "pass_rate": round(passed / len(scores) * 100, 1) if scores else None,
        "rows": rows,
        "question_stats": question_stats,
    }


def learner_quiz_summary(db: Session, learner_id: int) -> dict:
    """Résumé des résultats d'un apprenant, réutilisé par l'AI Tutor."""
    rows = list(
        db.execute(
            select(QuizAttempt, Quiz)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.learner_id == learner_id)
            .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())
        ).all()
    )
    if not rows:
        return {"attempts": 0, "by_category": {}, "recent": [], "weak_questions": [], "best": None, "worst": None}

    # Les lignes arrivent de la plus récente à la plus ancienne. Une reprise
    # réussie doit donc effacer une ancienne faiblesse, pas continuer à la
    # signaler indéfiniment. Les moyennes pédagogiques utilisent également la
    # dernière tentative de chaque quiz, sans surpondérer les répétitions.
    latest_by_quiz: dict[int, tuple[QuizAttempt, Quiz]] = {}
    latest_answers: dict[int, tuple[dict, Quiz]] = {}
    for attempt, quiz in rows:
        latest_by_quiz.setdefault(quiz.id, (attempt, quiz))
        for item in attempt.answers or []:
            question_id = item.get("question_id")
            if question_id is not None:
                latest_answers.setdefault(int(question_id), (item, quiz))

    by_category: dict[str, list[float]] = {}
    for attempt, quiz in latest_by_quiz.values():
        by_category.setdefault(quiz.category or "Général", []).append(attempt.score)

    weak_questions: list[dict] = []
    for item, quiz in latest_answers.values():
        if item.get("is_correct"):
            continue
        weak_questions.append(
            {
                "quiz": quiz.title,
                "category": quiz.category,
                "question": item.get("question_text"),
                "concept": item.get("concept"),
                "explanation": item.get("explanation"),
            }
        )

    latest_rows = list(latest_by_quiz.values())
    ordered = sorted(latest_rows, key=lambda row: row[0].score)
    return {
        "attempts": len(rows),
        "by_category": {
            cat: round(sum(values) / len(values), 1) for cat, values in by_category.items()
        },
        "recent": [
            {
                "quiz": quiz.title,
                "category": quiz.category,
                "score": attempt.score,
                "passed": attempt.passed,
                "date": attempt.submitted_at,
            }
            for attempt, quiz in rows[:5]
        ],
        "weak_questions": weak_questions[:5],
        "worst": {"quiz": ordered[0][1].title, "score": ordered[0][0].score},
        "best": {"quiz": ordered[-1][1].title, "score": ordered[-1][0].score},
    }


def pending_assignments(db: Session, learner_id: int) -> list[dict]:
    """Tous les quiz visibles et non réussis, exactement comme « Mes quiz »."""
    learner = db.get(Learner, learner_id)
    if learner is None:
        return []
    return [
        {
            "id": quiz["id"],
            "title": quiz["title"],
            "category": quiz["category"],
            "due_date": quiz["due_date"],
        }
        for quiz in available_quizzes(db, learner)
        if not quiz["passed"]
    ]


def assign_starter_quizzes(db: Session, learner: Learner) -> int:
    """Attribue le catalogue pertinent à un nouveau compte apprenant.

    Les quiz de sa filière et les quiz transversaux sont ajoutés sans doublon.
    La fonction ne commit pas afin que l'inscription reste atomique.
    """
    categories = ["Transversal"]
    if learner.course_category:
        categories.append(learner.course_category)
    quiz_ids = list(
        db.execute(
            select(Quiz.id).where(
                Quiz.is_published.is_(True), Quiz.category.in_(categories)
            )
        ).scalars()
    )
    if not quiz_ids:
        return 0

    existing = set(
        db.execute(
            select(QuizAssignment.quiz_id).where(
                QuizAssignment.learner_id == learner.id,
                QuizAssignment.quiz_id.in_(quiz_ids),
            )
        ).scalars()
    )
    for quiz_id in quiz_ids:
        if quiz_id not in existing:
            db.add(QuizAssignment(quiz_id=quiz_id, learner_id=learner.id))
    return len(set(quiz_ids) - existing)
