"""Tests des endpoints ne nécessitant pas de base de données.

Ces tests couvrent la partie historique du projet (analyse de profil,
recommandations, chatbot) et restent volontairement compatibles avec les tests
d'origine du prototype.
"""

from __future__ import annotations

import pytest

LEARNER_IN_DIFFICULTY = {
    "average_score": 45,
    "time_spent_hours": 12,
    "completion_rate": 40,
    "quiz_attempts": 5,
    "failed_quizzes": 3,
    "login_frequency": 2,
    "satisfaction_score": 2.5,
}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body and "models" in body
    # Les trois artefacts scikit-learn doivent être présents dans le dépôt.
    assert body["models"]["profile_classifier"] is True
    assert body["models"]["cluster_model"] is True
    assert body["models"]["scaler"] is True


def test_profile_analyze(client):
    response = client.post("/api/profile/analyze", json=LEARNER_IN_DIFFICULTY)
    assert response.status_code == 200
    body = response.json()
    assert "profile" in body
    assert body["risk_level"] in {"Faible", "Moyen", "Élevé"}
    # Le modèle entraîné doit être utilisé, pas le repli par règles.
    assert body["source"] == "model"
    assert body["cluster"] is not None
    assert 0.0 <= body["confidence"] <= 1.0


def test_profile_analyze_detects_difficulty(client):
    """Un apprenant nettement en échec doit être classé « En difficulté »."""
    response = client.post(
        "/api/profile/analyze",
        json={
            "average_score": 30,
            "time_spent_hours": 30,
            "completion_rate": 40,
            "quiz_attempts": 8,
            "failed_quizzes": 6,
            "login_frequency": 3,
            "satisfaction_score": 2.0,
        },
    )
    assert response.status_code == 200
    assert response.json()["profile"] == "En difficulté"


def test_profile_analyze_detects_advanced(client):
    response = client.post(
        "/api/profile/analyze",
        json={
            "average_score": 92,
            "time_spent_hours": 45,
            "completion_rate": 93,
            "quiz_attempts": 10,
            "failed_quizzes": 0,
            "login_frequency": 6,
            "satisfaction_score": 4.7,
        },
    )
    assert response.status_code == 200
    assert response.json()["profile"] == "Avancé"


def test_profile_analyze_rejects_out_of_range(client):
    payload = dict(LEARNER_IN_DIFFICULTY, average_score=150)
    response = client.post("/api/profile/analyze", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()
    # Aucune trace Python ne doit fuiter vers le client.
    assert "Traceback" not in response.text


def test_recommendations(client):
    payload = {
        "profile": "En difficulté",
        "average_score": 45,
        "completion_rate": 40,
        "failed_quizzes": 3,
        "satisfaction_score": 2.5,
    }
    response = client.post("/api/recommendations", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["recommended_content"]) > 0
    assert body["priority"] == "Haute"


@pytest.mark.parametrize(
    "profile,expected_priority",
    [("En difficulté", "Haute"), ("Peu actif", "Haute"), ("Avancé", "Normale"), ("Débutant", "Moyenne")],
)
def test_recommendations_priority_by_profile(client, profile, expected_priority):
    response = client.post(
        "/api/recommendations",
        json={
            "profile": profile,
            "average_score": 60,
            "completion_rate": 60,
            "failed_quizzes": 1,
            "satisfaction_score": 3.5,
        },
    )
    assert response.status_code == 200
    assert response.json()["priority"] == expected_priority


def test_chatbot(client):
    response = client.post(
        "/api/chatbot/ask",
        json={
            "question": "Pourquoi cette ressource est recommandée ?",
            "profile": "En difficulté",
            "recommended_content": "Cours de révision",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["answer"]) > 0


def test_chatbot_rejects_empty_question(client):
    response = client.post("/api/chatbot/ask", json={"question": "   ", "profile": "Moyen"})
    assert response.status_code == 422


def test_tutor_engine_is_declared_as_rule_based(client):
    """Le système ne doit jamais se présenter comme un LLM tant qu'aucun n'est branché."""
    response = client.get("/api/tutor/engine")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "rules"
    assert body["is_llm"] is False


def test_openapi_schema_is_valid(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/profile/analyze" in response.json()["paths"]
