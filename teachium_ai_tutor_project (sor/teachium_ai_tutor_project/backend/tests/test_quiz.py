"""Tests du système de quiz et de la bibliothèque de cours.

Le point vérifié en priorité : **l'apprenant ne peut jamais fixer sa propre
note**. Il n'a accès ni aux bonnes réponses avant correction, ni à une route de
saisie de note, et le champ `score` envoyé dans une copie est ignoré.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import auth_header

TRAINER = {"email": "formateur@teachium.ma", "password": "Formateur@2026"}


@pytest.fixture
def trainer_token(client, require_db) -> str:
    response = client.post("/api/auth/login", json=TRAINER)
    if response.status_code != 200:
        pytest.skip("Comptes de démonstration absents : lancez scripts/seed_users.py")
    return response.json()["access_token"]


@pytest.fixture
def sample_quiz(client, trainer_token):
    """Crée un quiz jetable, publié, puis le supprime en fin de test."""
    payload = {
        "title": f"Quiz pytest {uuid.uuid4().hex[:8]}",
        "category": "Python",
        "difficulty": "Facile",
        "passing_score": 50,
        "is_published": True,
        "questions": [
            {
                "question_text": "Quel mot-clé définit une fonction en Python ?",
                "options": ["function", "def", "fun"],
                "correct_index": 1,
                "explanation": "En Python, une fonction se déclare avec def.",
            },
            {
                "question_text": "Quel type représente un nombre décimal ?",
                "options": ["int", "float"],
                "correct_index": 1,
            },
        ],
    }
    response = client.post("/api/quizzes", headers=auth_header(trainer_token), json=payload)
    assert response.status_code == 201, response.text
    quiz = response.json()
    yield quiz
    client.delete(f"/api/quizzes/{quiz['id']}", headers=auth_header(trainer_token))


# --- Création et droits -----------------------------------------------------


def test_trainer_creates_quiz_with_questions(sample_quiz):
    assert sample_quiz["question_count"] == 2
    assert sample_quiz["is_published"] is True
    assert sample_quiz["questions"][0]["correct_index"] == 1


def test_learner_cannot_create_a_quiz(client, temp_user):
    response = client.post(
        "/api/quizzes",
        headers=auth_header(temp_user["access_token"]),
        json={
            "title": "Quiz interdit",
            "questions": [{"question_text": "Une question ?", "options": ["a", "b"], "correct_index": 0}],
        },
    )
    assert response.status_code == 403


def test_quiz_validation_rejects_bad_questions(client, trainer_token):
    headers = auth_header(trainer_token)
    base = {"title": "Quiz invalide"}

    out_of_range = {"question_text": "Une question ?", "options": ["a", "b"], "correct_index": 5}
    assert client.post("/api/quizzes", headers=headers, json={**base, "questions": [out_of_range]}).status_code == 422

    duplicates = {"question_text": "Une question ?", "options": ["a", "a"], "correct_index": 0}
    assert client.post("/api/quizzes", headers=headers, json={**base, "questions": [duplicates]}).status_code == 422

    single = {"question_text": "Une question ?", "options": ["a"], "correct_index": 0}
    assert client.post("/api/quizzes", headers=headers, json={**base, "questions": [single]}).status_code == 422


# --- Passage et correction --------------------------------------------------


def test_correct_answers_are_never_sent_before_submission(client, trainer_token, temp_user, sample_quiz):
    """Le point le plus sensible : la bonne réponse ne doit pas fuiter."""
    learner_id = temp_user["user"]["learner_id"]
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                headers=auth_header(trainer_token), json={"learner_ids": [learner_id]})

    response = client.get(f"/api/quizzes/{sample_quiz['id']}/take",
                          headers=auth_header(temp_user["access_token"]))
    assert response.status_code == 200
    assert "correct_index" not in response.text
    assert "explanation" not in response.text
    for question in response.json()["questions"]:
        assert set(question.keys()) == {"id", "position", "question_text", "options", "points"}


def test_server_grades_the_copy_and_ignores_any_submitted_score(
    client, trainer_token, temp_user, sample_quiz
):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(temp_user["access_token"])
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                headers=auth_header(trainer_token), json={"learner_ids": [learner_id]})

    quiz = client.get(f"/api/quizzes/{sample_quiz['id']}/take", headers=headers).json()

    # Toutes les réponses fausses, mais on tente d'imposer une note de 100.
    wrong = [{"question_id": q["id"], "chosen_index": 0} for q in quiz["questions"]]
    response = client.post(
        f"/api/quizzes/{sample_quiz['id']}/submit", headers=headers,
        json={"score": 100, "passed": True, "answers": wrong},
    )
    assert response.status_code == 201
    attempt = response.json()["attempt"]
    assert attempt["score"] == 0.0, "La note envoyée par le client a été prise en compte !"
    assert attempt["passed"] is False
    assert attempt["correct_count"] == 0

    # Réponses correctes : le serveur calcule 100.
    good = [{"question_id": q["id"], "chosen_index": 1} for q in quiz["questions"]]
    attempt = client.post(
        f"/api/quizzes/{sample_quiz['id']}/submit", headers=headers, json={"answers": good}
    ).json()["attempt"]
    assert attempt["score"] == 100.0
    assert attempt["passed"] is True
    assert all(a["is_correct"] for a in attempt["answers"])


def test_grading_updates_metrics_and_reruns_the_models(
    client, trainer_token, temp_user, sample_quiz
):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(temp_user["access_token"])
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                headers=auth_header(trainer_token), json={"learner_ids": [learner_id]})

    before = client.get("/api/learners/me", headers=headers).json()["learner"]
    quiz = client.get(f"/api/quizzes/{sample_quiz['id']}/take", headers=headers).json()
    good = [{"question_id": q["id"], "chosen_index": 1} for q in quiz["questions"]]
    client.post(f"/api/quizzes/{sample_quiz['id']}/submit", headers=headers, json={"answers": good})

    after = client.get("/api/learners/me", headers=headers).json()["learner"]
    assert after["quiz_attempts"] == before["quiz_attempts"] + 1
    assert after["average_score"] > before["average_score"]
    # Une nouvelle analyse ML a été enregistrée.
    assert len(after["profile_history"]) > len(before["profile_history"])


def test_failed_quiz_increments_failure_counter(client, trainer_token, temp_user, sample_quiz):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(temp_user["access_token"])
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                headers=auth_header(trainer_token), json={"learner_ids": [learner_id]})

    before = client.get("/api/learners/me", headers=headers).json()["learner"]
    quiz = client.get(f"/api/quizzes/{sample_quiz['id']}/take", headers=headers).json()
    wrong = [{"question_id": q["id"], "chosen_index": 0} for q in quiz["questions"]]
    client.post(f"/api/quizzes/{sample_quiz['id']}/submit", headers=headers, json={"answers": wrong})

    after = client.get("/api/learners/me", headers=headers).json()["learner"]
    assert after["failed_quizzes"] == before["failed_quizzes"] + 1


def test_learner_cannot_edit_server_owned_metrics(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    before = client.get("/api/learners/me", headers=headers).json()["learner"]
    response = client.patch(
        "/api/learners/me",
        headers=headers,
        json={"average_score": 100, "quiz_attempts": 999, "failed_quizzes": 0},
    )
    assert response.status_code in (403, 405, 422)
    after = client.get("/api/learners/me", headers=headers).json()["learner"]
    assert after["average_score"] == before["average_score"]
    assert after["quiz_attempts"] == before["quiz_attempts"]
    assert after["failed_quizzes"] == before["failed_quizzes"]


def test_learner_can_take_a_published_quiz_in_own_category(
    client, trainer_token, temp_user, sample_quiz
):
    """Un quiz publié dans la filière reste visible même avant attribution."""
    response = client.get(f"/api/quizzes/{sample_quiz['id']}/take",
                          headers=auth_header(temp_user["access_token"]))
    assert response.status_code == 200


def test_answers_from_another_quiz_are_rejected(client, trainer_token, temp_user, sample_quiz):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(temp_user["access_token"])
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                headers=auth_header(trainer_token), json={"learner_ids": [learner_id]})

    response = client.post(
        f"/api/quizzes/{sample_quiz['id']}/submit", headers=headers,
        json={"answers": [{"question_id": 999999, "chosen_index": 0}]},
    )
    assert response.status_code == 422


# --- Attribution et résultats ----------------------------------------------


def test_assignment_is_idempotent(client, trainer_token, temp_user, sample_quiz):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(trainer_token)

    first = client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                        headers=headers, json={"learner_ids": [learner_id]}).json()
    assert first["assigned"] == 1

    second = client.post(f"/api/quizzes/{sample_quiz['id']}/assign",
                         headers=headers, json={"learner_ids": [learner_id]}).json()
    assert second["assigned"] == 0
    assert second["already_assigned"] == 1


def test_trainer_sees_results(client, trainer_token, temp_user, sample_quiz):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(trainer_token)
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign", headers=headers,
                json={"learner_ids": [learner_id]})

    quiz = client.get(f"/api/quizzes/{sample_quiz['id']}/take",
                      headers=auth_header(temp_user["access_token"])).json()
    client.post(f"/api/quizzes/{sample_quiz['id']}/submit",
                headers=auth_header(temp_user["access_token"]),
                json={"answers": [{"question_id": q["id"], "chosen_index": 1} for q in quiz["questions"]]})

    results = client.get(f"/api/quizzes/{sample_quiz['id']}/results", headers=headers).json()
    assert results["assigned_count"] >= 1
    assert results["participants"] >= 1
    assert results["average_score"] == 100.0
    assert len(results["question_stats"]) == 2


def test_questions_cannot_be_changed_after_an_attempt(client, trainer_token, temp_user, sample_quiz):
    learner_id = temp_user["user"]["learner_id"]
    headers = auth_header(trainer_token)
    client.post(f"/api/quizzes/{sample_quiz['id']}/assign", headers=headers,
                json={"learner_ids": [learner_id]})
    quiz = client.get(f"/api/quizzes/{sample_quiz['id']}/take",
                      headers=auth_header(temp_user["access_token"])).json()
    client.post(f"/api/quizzes/{sample_quiz['id']}/submit",
                headers=auth_header(temp_user["access_token"]),
                json={"answers": [{"question_id": q["id"], "chosen_index": 0} for q in quiz["questions"]]})

    response = client.patch(
        f"/api/quizzes/{sample_quiz['id']}", headers=headers,
        json={"questions": [{"question_text": "Nouvelle question ?", "options": ["a", "b"], "correct_index": 0}]},
    )
    assert response.status_code == 409


# --- Évaluation saisie par le formateur -------------------------------------


def test_trainer_records_offline_evaluation(client, trainer_token, temp_user):
    learner_id = temp_user["user"]["learner_id"]
    before = client.get("/api/learners/me", headers=auth_header(temp_user["access_token"])).json()["learner"]

    response = client.post(
        f"/api/learners/{learner_id}/evaluations", headers=auth_header(trainer_token),
        json={"score": 80, "title": "Examen blanc"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["score"] == 80
    assert body["new_profile"] is not None

    after = client.get("/api/learners/me", headers=auth_header(temp_user["access_token"])).json()["learner"]
    assert after["quiz_attempts"] == before["quiz_attempts"] + 1


def test_offline_evaluation_rejects_out_of_range_score(client, trainer_token, temp_user):
    learner_id = temp_user["user"]["learner_id"]
    response = client.post(
        f"/api/learners/{learner_id}/evaluations", headers=auth_header(trainer_token), json={"score": 150}
    )
    assert response.status_code == 422


# --- Bibliothèque de cours --------------------------------------------------


def test_learner_can_read_but_not_write_courses(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    assert client.get("/api/courses", headers=headers).status_code == 200
    assert client.post("/api/courses", headers=headers, json={
        "title": "Fiche interdite", "category": "Python",
        "content": "Un contenu suffisamment long pour passer la validation Pydantic.",
    }).status_code == 403


def test_course_search_returns_relevant_results(client, trainer_token):
    headers = auth_header(trainer_token)
    if not client.get("/api/courses", headers=headers).json():
        pytest.skip("Bibliothèque vide : lancez scripts/seed_content.py")

    hits = client.get("/api/courses/search", headers=headers,
                      params={"q": "à quoi sert la normalisation avant K-Means ?"}).json()
    assert hits, "La recherche TF-IDF ne renvoie aucun résultat"
    assert "K-Means" in hits[0]["title"]
    assert hits[0]["score"] > 0
    assert len(hits[0]["passage"]) > 20


def test_tutor_answers_course_questions_from_the_library(client, temp_user, trainer_token):
    headers = auth_header(temp_user["access_token"])
    if not client.get("/api/courses", headers=headers).json():
        pytest.skip("Bibliothèque vide : lancez scripts/seed_content.py")

    answer = client.post("/api/chat/ask", headers=headers,
                         json={"question": "C'est quoi une boucle for en Python ?"}).json()["answer"]
    assert "fiche" in answer.lower(), answer[:200]
    assert "boucle" in answer.lower()


def test_tutor_admits_when_it_does_not_know(client, temp_user):
    """Le tuteur ne doit jamais inventer une réponse hors de son périmètre."""
    answer = client.post(
        "/api/chat/ask", headers=auth_header(temp_user["access_token"]),
        json={"question": "Quelle est la recette traditionnelle du couscous royal ?"},
    ).json()["answer"]
    assert "pas trouvé" in answer.lower() or "reformulez" in answer.lower()
