from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_profile_analyze():
    payload = {
        "average_score": 45,
        "time_spent_hours": 12,
        "completion_rate": 40,
        "quiz_attempts": 5,
        "failed_quizzes": 3,
        "login_frequency": 2,
        "satisfaction_score": 2.5,
    }
    response = client.post("/api/profile/analyze", json=payload)
    assert response.status_code == 200
    assert "profile" in response.json()


def test_recommendations():
    payload = {
        "profile": "En difficulté",
        "average_score": 45,
        "completion_rate": 40,
        "failed_quizzes": 3,
        "satisfaction_score": 2.5,
    }
    response = client.post("/api/recommendations", json=payload)
    assert response.status_code == 200
    assert len(response.json()["recommended_content"]) > 0
