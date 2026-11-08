"""Tests de la chaîne complète : profil → recommandations → AI Tutor → historique."""

from __future__ import annotations

from tests.conftest import auth_header


def test_learner_dashboard_returns_ml_profile(client, temp_user):
    response = client.get("/api/learners/me", headers=auth_header(temp_user["access_token"]))
    assert response.status_code == 200
    learner = response.json()["learner"]
    assert learner["profile"] is not None
    assert learner["risk_level"] in {"Faible", "Moyen", "Élevé"}
    # Le profil est calculé par les modèles, pas saisi à la main.
    assert learner["cluster"] is not None


def test_learner_cannot_record_a_score_for_themselves(client, temp_user):
    """Règle métier centrale : un apprenant ne peut jamais s'auto-attribuer une note."""
    headers = auth_header(temp_user["access_token"])

    # L'ancienne route de saisie a été supprimée.
    assert client.post(
        "/api/learners/me/activity",
        headers=headers,
        json={"activity_type": "quiz", "score": 100},
    ).status_code == 405

    # La saisie d'une évaluation est réservée aux formateurs.
    learner_id = temp_user["user"]["learner_id"]
    assert client.post(
        f"/api/learners/{learner_id}/evaluations", headers=headers, json={"score": 100}
    ).status_code == 403


def test_recommendations_are_generated_and_can_be_completed(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    recos = client.get("/api/recommendations/me", headers=headers).json()
    assert len(recos) > 0
    assert recos[0]["completed"] is False

    reco_id = recos[0]["id"]
    done = client.post(
        f"/api/recommendations/{reco_id}/complete", headers=headers, json={"completed": True}
    )
    assert done.status_code == 200
    assert done.json()["completed"] is True
    assert done.json()["completed_at"] is not None


def test_cannot_complete_someone_elses_recommendation(client, temp_user):
    response = client.post(
        "/api/recommendations/999999/complete",
        headers=auth_header(temp_user["access_token"]),
        json={"completed": True},
    )
    assert response.status_code == 404


def test_tutor_answers_and_persists_history(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    client.delete("/api/chat/history", headers=headers)

    response = client.post("/api/chat/ask", headers=headers, json={"question": "Quel est mon profil ?"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["answer"]) > 0
    assert body["engine"] == "rules"
    # La réponse doit citer le profil réellement calculé.
    assert body["profile"] in body["answer"]

    history = client.get("/api/chat/history", headers=headers).json()
    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"


def test_tutor_uses_real_learner_numbers(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    learner = client.get("/api/learners/me", headers=headers).json()["learner"]
    answer = client.post(
        "/api/chat/ask", headers=headers, json={"question": "Quel est mon score moyen ?"}
    ).json()["answer"]
    assert f"{learner['average_score']:.1f}" in answer


def test_tutor_explains_recommendations(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    recos = client.get("/api/recommendations/me", headers=headers).json()
    answer = client.post(
        "/api/chat/ask",
        headers=headers,
        json={"question": "Pourquoi ai-je reçu cette recommandation ?"},
    ).json()["answer"]
    assert recos[0]["content"] in answer


def test_empty_question_is_rejected(client, temp_user):
    response = client.post(
        "/api/chat/ask", headers=auth_header(temp_user["access_token"]), json={"question": "   "}
    )
    assert response.status_code == 422


def test_clear_history(client, temp_user):
    headers = auth_header(temp_user["access_token"])
    client.post("/api/chat/ask", headers=headers, json={"question": "Bonjour"})
    client.delete("/api/chat/history", headers=headers)
    assert client.get("/api/chat/history", headers=headers).json()["messages"] == []


def test_trainer_dashboard_statistics(client, require_db):
    login = client.post(
        "/api/auth/login", json={"email": "formateur@teachium.ma", "password": "Formateur@2026"}
    )
    if login.status_code != 200:
        import pytest

        pytest.skip("Comptes de démonstration absents : lancez scripts/seed_users.py")

    headers = auth_header(login.json()["access_token"])
    stats = client.get("/api/dashboard/stats", headers=headers).json()
    assert stats["source"] in {"database", "csv_fallback"}
    assert stats["total_learners"] > 0
    assert sum(stats["learners_by_profile"].values()) > 0
    assert len(stats["score_histogram"]) == 5

    listing = client.get("/api/learners?page_size=5", headers=headers).json()
    assert listing["page_size"] == 5
    assert len(listing["items"]) <= 5
    assert listing["total"] >= len(listing["items"])

    metrics = client.get("/api/model/evaluate", headers=headers).json()
    assert 0 <= metrics["accuracy"] <= 1
    assert metrics["decision_tree"]["type"] == "DecisionTreeClassifier"
    assert len(metrics["feature_importances"]) == 7
