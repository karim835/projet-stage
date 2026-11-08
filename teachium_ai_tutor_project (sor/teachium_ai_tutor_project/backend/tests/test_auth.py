"""Tests d'authentification, de hachage et de contrôle des rôles."""

from __future__ import annotations

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from tests.conftest import auth_header


# --- Unitaires (aucune base requise) ----------------------------------------


def test_password_is_hashed_not_stored_in_clear():
    password = "MonMotDePasse123"
    hashed = hash_password(password)
    assert hashed != password
    assert password not in hashed
    assert hashed.startswith("$2")  # préfixe bcrypt
    assert verify_password(password, hashed)
    assert not verify_password("MauvaisMotDePasse", hashed)


def test_two_hashes_of_same_password_differ():
    """Le sel bcrypt doit rendre chaque empreinte unique."""
    assert hash_password("identique") != hash_password("identique")


def test_password_too_long_is_rejected():
    with pytest.raises(ValueError):
        hash_password("a" * 100)


def test_jwt_round_trip():
    token = create_access_token(42, "trainer", {"email": "x@y.z"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "trainer"


def test_tampered_jwt_is_rejected():
    token = create_access_token(1, "administrator")
    with pytest.raises(TokenError):
        decode_access_token(token[:-4] + "abcd")


# --- Intégration (base de données requise) ----------------------------------


def test_register_and_login(client, temp_user):
    assert temp_user["token_type"] == "bearer"
    assert temp_user["user"]["role"] == "learner"
    # Un compte apprenant reçoit automatiquement une fiche pédagogique.
    assert temp_user["user"]["student_id"] is not None

    response = client.post(
        "/api/auth/login", json={"email": temp_user["email"], "password": temp_user["password"]}
    )
    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client, temp_user):
    response = client.post(
        "/api/auth/login", json={"email": temp_user["email"], "password": "MauvaisMotDePasse"}
    )
    assert response.status_code == 401


def test_login_does_not_reveal_whether_email_exists(client, require_db, temp_user):
    unknown = client.post(
        "/api/auth/login", json={"email": "inconnu@teachium-tests.ma", "password": "peuimporte"}
    )
    wrong = client.post(
        "/api/auth/login", json={"email": temp_user["email"], "password": "mauvais"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_duplicate_email_is_rejected(client, temp_user):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Doublon",
            "email": temp_user["email"],
            "password": "MotDePasseTest123",
            "role": "learner",
            "course_category": "Python",
        },
    )
    assert response.status_code == 409


def test_public_registration_rejects_privileged_roles(client, require_db):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Compte interdit",
            "email": "privileged-public@teachium-tests.ma",
            "password": "MotDePasseTest123",
            "role": "administrator",
            "course_category": "Python",
        },
    )
    assert response.status_code == 422


def test_protected_route_requires_token(client, require_db):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/learners/me").status_code == 401
    assert client.get("/api/dashboard/stats").status_code == 401


def test_invalid_token_is_rejected(client, require_db):
    response = client.get("/api/auth/me", headers=auth_header("ceci.nest.pas.un.jeton"))
    assert response.status_code == 401


def test_learner_cannot_access_trainer_routes(client, temp_user):
    token = temp_user["access_token"]
    assert client.get("/api/learners", headers=auth_header(token)).status_code == 403
    assert client.get("/api/dashboard/stats", headers=auth_header(token)).status_code == 403
    assert client.get("/api/admin/overview", headers=auth_header(token)).status_code == 403


def test_change_password_requires_current_password(client, temp_user):
    response = client.post(
        "/api/auth/change-password",
        headers=auth_header(temp_user["access_token"]),
        json={"current_password": "faux", "new_password": "NouveauMotDePasse1"},
    )
    assert response.status_code == 400
