"""Routes des quiz.

Séparation stricte des responsabilités :

* **Formateur / administrateur** — crée, modifie, publie, attribue les quiz,
  consulte les résultats et peut saisir la note d'une évaluation hors ligne.
* **Apprenant** — consulte les quiz qui lui sont ouverts, les passe et reçoit
  sa correction. Il n'a **aucun** moyen de saisir ou d'influencer une note :
  il ne transmet que des index de réponses.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentLearner, DbSession, TrainerUser
from app.db.models import CourseResource, Learner, Quiz, QuizAssignment, QuizAttempt, QuizQuestion
from app.schemas.quiz import (
    AssignInput,
    AssignResult,
    AttemptReview,
    AttemptResult,
    AttemptSubmit,
    AttemptSummary,
    AttemptWithProfile,
    LearnerQuizCard,
    ManualEvaluationInput,
    QuizForLearner,
    QuizHintResponse,
    QuizFull,
    QuizInput,
    QuizResults,
    QuizSummary,
    QuizUpdate,
)
from app.services import quiz_service, tutor_service
from app.services.quiz_service import QuizError

router = APIRouter(tags=["Quiz"])


# ===========================================================================
#  Espace apprenant
# ===========================================================================


@router.get(
    "/api/quizzes/me",
    response_model=list[LearnerQuizCard],
    tags=["Quiz — apprenant"],
    summary="Quiz ouverts à l'apprenant connecté",
)
def my_quizzes(learner: CurrentLearner, db: DbSession):
    return quiz_service.available_quizzes(db, learner)


@router.get(
    "/api/quizzes/me/attempts",
    response_model=list[AttemptSummary],
    tags=["Quiz — apprenant"],
    summary="Historique des quiz passés",
)
def my_attempts(learner: CurrentLearner, db: DbSession, limit: int = Query(50, ge=1, le=200)):
    rows = db.execute(
        select(QuizAttempt, Quiz.title)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(QuizAttempt.learner_id == learner.id)
        .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())
        .limit(limit)
    ).all()
    return [
        AttemptSummary(
            id=a.id, quiz_id=a.quiz_id, quiz_title=title, score=a.score,
            correct_count=a.correct_count, total_questions=a.total_questions,
            passed=a.passed, duration_seconds=a.duration_seconds, submitted_at=a.submitted_at,
        )
        for a, title in rows
    ]


def _learner_can_access(db: DbSession, learner: Learner, quiz: Quiz) -> bool:
    if not quiz.is_published:
        return False
    if learner.course_category and quiz.category == learner.course_category:
        return True
    assigned = db.execute(
        select(func.count(QuizAssignment.id)).where(
            QuizAssignment.quiz_id == quiz.id, QuizAssignment.learner_id == learner.id
        )
    ).scalar_one()
    return bool(assigned)


@router.get(
    "/api/quizzes/{quiz_id}/take",
    response_model=QuizForLearner,
    tags=["Quiz — apprenant"],
    summary="Ouvrir un quiz (sans les bonnes réponses)",
)
def take_quiz(learner: CurrentLearner, db: DbSession, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    if not _learner_can_access(db, learner, quiz):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce quiz ne vous est pas attribué et n'est pas ouvert à votre filière.",
        )
    if not quiz.questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce quiz ne contient aucune question. Contactez votre formateur.",
        )
    return quiz_service.quiz_for_taking(db, quiz)


@router.get(
    "/api/quizzes/{quiz_id}/questions/{question_id}/hint",
    response_model=QuizHintResponse,
    tags=["Quiz — apprenant"],
    summary="Demander un indice sans révéler la bonne réponse",
)
def get_hint(
    learner: CurrentLearner,
    db: DbSession,
    quiz_id: int = Path(..., ge=1),
    question_id: int = Path(..., ge=1),
):
    quiz = quiz_service.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    if not _learner_can_access(db, learner, quiz):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce quiz ne vous est pas attribué et n'est pas ouvert à votre filière.",
        )
    try:
        return quiz_service.question_hint(db, quiz, question_id)
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/quizzes/{quiz_id}/submit",
    response_model=AttemptWithProfile,
    status_code=status.HTTP_201_CREATED,
    tags=["Quiz — apprenant"],
    summary="Soumettre ses réponses (correction automatique côté serveur)",
)
def submit_quiz(
    payload: AttemptSubmit,
    learner: CurrentLearner,
    db: DbSession,
    quiz_id: int = Path(..., ge=1),
):
    """L'apprenant n'envoie que des index de réponses.

    La note est calculée par le serveur : il est impossible de la fournir ou de
    la modifier depuis le client.
    """
    quiz = quiz_service.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    if not _learner_can_access(db, learner, quiz):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce quiz ne vous est pas attribué et n'est pas ouvert à votre filière.",
        )

    questions_by_id = {q.id: q for q in quiz.questions}
    valid_ids = set(questions_by_id)
    unknown = [a.question_id for a in payload.answers if a.question_id not in valid_ids]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La copie contient des questions qui n'appartiennent pas à ce quiz.",
        )

    invalid_choices = [
        answer.question_id
        for answer in payload.answers
        if answer.chosen_index is not None
        and answer.chosen_index >= len(questions_by_id[answer.question_id].options or [])
    ]
    if invalid_choices:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Une réponse choisie n'existe pas parmi les propositions de la question.",
        )

    previous = tutor_service.latest_profile(db, learner.id)
    previous_profile = previous.profile if previous else None

    answers = {a.question_id: a.chosen_index for a in payload.answers}
    try:
        attempt = quiz_service.grade_attempt(db, learner, quiz, answers, payload.started_at)
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    current = tutor_service.latest_profile(db, learner.id)
    new_profile = current.profile if current else None
    feedback = quiz_service.tutor_feedback(db, quiz, attempt)

    return AttemptWithProfile(
        attempt=AttemptResult.model_validate(attempt),
        previous_profile=previous_profile,
        new_profile=new_profile,
        profile_changed=bool(previous_profile and new_profile and previous_profile != new_profile),
        average_score=learner.average_score,
        completion_rate=learner.completion_rate,
        quiz_attempts=learner.quiz_attempts,
        tutor_feedback=feedback,
    )


@router.get(
    "/api/quizzes/attempts/{attempt_id}",
    response_model=AttemptReview,
    tags=["Quiz — apprenant"],
    summary="Revoir la correction d'une copie",
)
def attempt_detail(learner: CurrentLearner, db: DbSession, attempt_id: int = Path(..., ge=1)):
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.learner_id != learner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copie introuvable.")
    quiz = quiz_service.get_quiz(db, attempt.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    base = AttemptResult.model_validate(attempt)
    return AttemptReview(**base.model_dump(), tutor_feedback=quiz_service.tutor_feedback(db, quiz, attempt))


# ===========================================================================
#  Espace formateur / administrateur
# ===========================================================================


def _summary(db: DbSession, quiz: Quiz) -> QuizSummary:
    question_count = db.execute(
        select(func.count(QuizQuestion.id)).where(QuizQuestion.quiz_id == quiz.id)
    ).scalar_one()
    assigned = db.execute(
        select(func.count(QuizAssignment.id)).where(QuizAssignment.quiz_id == quiz.id)
    ).scalar_one()
    attempts_count, average = db.execute(
        select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score)).where(
            QuizAttempt.quiz_id == quiz.id
        )
    ).one()

    return QuizSummary(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        category=quiz.category,
        difficulty=quiz.difficulty,
        passing_score=quiz.passing_score,
        is_published=quiz.is_published,
        course_resource_id=quiz.course_resource_id,
        question_count=int(question_count or 0),
        assigned_count=int(assigned or 0),
        attempts_count=int(attempts_count or 0),
        average_score=round(float(average), 2) if average is not None else None,
        created_by=quiz.created_by.name if quiz.created_by else None,
        created_at=quiz.created_at,
    )


@router.get("/api/quizzes", response_model=list[QuizSummary], summary="Lister les quiz (formateur)")
def list_quizzes(
    db: DbSession,
    _: TrainerUser,
    category: str | None = Query(None, max_length=60),
    published: bool | None = Query(None),
):
    stmt = select(Quiz).options(selectinload(Quiz.created_by))
    if category:
        stmt = stmt.where(Quiz.category == category)
    if published is not None:
        stmt = stmt.where(Quiz.is_published.is_(published))
    quizzes = db.execute(stmt.order_by(Quiz.created_at.desc())).scalars().all()
    return [_summary(db, quiz) for quiz in quizzes]


@router.post(
    "/api/quizzes",
    response_model=QuizFull,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un quiz",
)
def create_quiz(payload: QuizInput, db: DbSession, user: TrainerUser):
    if payload.course_resource_id is not None and db.get(CourseResource, payload.course_resource_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fiche de cours liée est introuvable.",
        )
    quiz = Quiz(
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        category=(payload.category or "").strip() or None,
        passing_score=payload.passing_score,
        difficulty=payload.difficulty,
        is_published=payload.is_published,
        created_by_id=user.id,
        course_resource_id=payload.course_resource_id,
    )
    db.add(quiz)
    db.flush()

    for position, question in enumerate(payload.questions):
        db.add(
            QuizQuestion(
                quiz_id=quiz.id,
                position=position,
                question_text=question.question_text.strip(),
                options=question.options,
                correct_index=question.correct_index,
                points=question.points,
                concept=(question.concept or "").strip() or None,
                hint=(question.hint or "").strip() or None,
                explanation=(question.explanation or "").strip() or None,
            )
        )

    db.commit()
    db.refresh(quiz)
    return _full(db, quiz)


def _full(db: DbSession, quiz: Quiz) -> QuizFull:
    summary = _summary(db, quiz)
    questions = sorted(quiz.questions, key=lambda q: (q.position, q.id))
    return QuizFull(**summary.model_dump(), questions=[
        {
            "id": q.id, "position": q.position, "question_text": q.question_text,
            "options": list(q.options or []), "points": q.points,
            "correct_index": q.correct_index, "concept": q.concept,
            "hint": q.hint, "explanation": q.explanation,
        }
        for q in questions
    ])


@router.get("/api/quizzes/{quiz_id}", response_model=QuizFull, summary="Détail complet d'un quiz")
def quiz_detail(db: DbSession, _: TrainerUser, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    return _full(db, quiz)


@router.patch("/api/quizzes/{quiz_id}", response_model=QuizFull, summary="Modifier un quiz")
def update_quiz(payload: QuizUpdate, db: DbSession, _: TrainerUser, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie."
        )

    questions = data.pop("questions", None)
    for key, value in data.items():
        if key == "course_resource_id":
            if value is not None and db.get(CourseResource, value) is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La fiche de cours liée est introuvable.",
                )
            # ``null`` permet explicitement de retirer un ancien lien.
            quiz.course_resource_id = value
        elif value is not None:
            setattr(quiz, key, value)

    if questions is not None:
        # Le remplacement des questions invalide les copies déjà corrigées :
        # on refuse si le quiz a déjà été passé, pour ne pas fausser l'historique.
        existing_attempts = db.execute(
            select(func.count(QuizAttempt.id)).where(QuizAttempt.quiz_id == quiz.id)
        ).scalar_one()
        if existing_attempts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ce quiz a déjà été passé {existing_attempts} fois : ses questions ne "
                    "peuvent plus être modifiées. Créez un nouveau quiz pour une version révisée."
                ),
            )
        for question in list(quiz.questions):
            db.delete(question)
        db.flush()
        for position, question in enumerate(questions):
            db.add(
                QuizQuestion(
                    quiz_id=quiz.id,
                    position=position,
                    question_text=question["question_text"].strip(),
                    options=question["options"],
                    correct_index=question["correct_index"],
                    points=question["points"],
                    concept=(question.get("concept") or "").strip() or None,
                    hint=(question.get("hint") or "").strip() or None,
                    explanation=(question.get("explanation") or "").strip() or None,
                )
            )

    db.commit()
    db.refresh(quiz)
    return _full(db, quiz)


@router.delete("/api/quizzes/{quiz_id}", summary="Supprimer un quiz")
def delete_quiz(db: DbSession, _: TrainerUser, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id, with_questions=False)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")

    attempts = db.execute(
        select(func.count(QuizAttempt.id)).where(QuizAttempt.quiz_id == quiz.id)
    ).scalar_one()
    title = quiz.title
    db.delete(quiz)
    db.commit()
    return {
        "message": f"Quiz « {title} » supprimé."
        + (f" {attempts} copie(s) associée(s) ont également été effacées." if attempts else "")
    }


@router.post(
    "/api/quizzes/{quiz_id}/assign",
    response_model=AssignResult,
    summary="Attribuer un quiz à des apprenants",
)
def assign(payload: AssignInput, db: DbSession, user: TrainerUser, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id, with_questions=False)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    if not quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publiez le quiz avant de l'attribuer : un quiz non publié reste invisible.",
        )
    return quiz_service.assign_quiz(
        db, quiz, payload.learner_ids, user.id, due_date=payload.due_date
    )


@router.delete(
    "/api/quizzes/{quiz_id}/assign/{learner_id}",
    summary="Retirer l'attribution d'un quiz à un apprenant",
)
def unassign(
    db: DbSession,
    _: TrainerUser,
    quiz_id: int = Path(..., ge=1),
    learner_id: int = Path(..., ge=1),
):
    quiz = quiz_service.get_quiz(db, quiz_id, with_questions=False)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    if not quiz_service.unassign_quiz(db, quiz, learner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cet apprenant n'a pas ce quiz attribué."
        )
    return {"message": "Attribution retirée."}


@router.get(
    "/api/quizzes/{quiz_id}/results",
    response_model=QuizResults,
    summary="Résultats détaillés d'un quiz",
)
def results(db: DbSession, _: TrainerUser, quiz_id: int = Path(..., ge=1)):
    quiz = quiz_service.get_quiz(db, quiz_id, with_questions=False)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz introuvable.")
    return quiz_service.quiz_results(db, quiz)


@router.post(
    "/api/learners/{learner_id}/evaluations",
    status_code=status.HTTP_201_CREATED,
    tags=["Quiz"],
    summary="Saisir la note d'une évaluation hors ligne (formateur)",
)
def manual_evaluation(
    payload: ManualEvaluationInput,
    db: DbSession,
    _: TrainerUser,
    learner_id: int = Path(..., ge=1),
):
    """Réservé aux formateurs : note d'un devoir ou d'un examen en présentiel.

    Les apprenants n'ont pas accès à cette route — ils ne peuvent en aucun cas
    enregistrer une note eux-mêmes.
    """
    learner = db.get(Learner, learner_id)
    if learner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Apprenant introuvable.")

    previous = tutor_service.latest_profile(db, learner.id)
    try:
        activity = quiz_service.record_manual_evaluation(
            db,
            learner,
            score=payload.score,
            title=payload.title,
            duration_minutes=payload.duration_minutes,
            passing_score=payload.passing_score,
        )
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    current = tutor_service.latest_profile(db, learner.id)
    return {
        "activity_id": activity.id,
        "score": activity.score,
        "average_score": learner.average_score,
        "previous_profile": previous.profile if previous else None,
        "new_profile": current.profile if current else None,
        "message": (
            f"Évaluation enregistrée. Nouvelle moyenne : {learner.average_score}/100. "
            f"Profil : {current.profile if current else 'non calculé'}."
        ),
    }
