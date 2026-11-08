"""Configuration commune des tests.

Les tests sont séparés en deux familles :

* ceux qui n'ont besoin **d'aucune base de données** (modèles ML, validation,
  sécurité) — ils s'exécutent toujours ;
* ceux qui nécessitent PostgreSQL/Neon — ils sont automatiquement ignorés
  (`skip`) avec un message explicite si `DATABASE_URL` est absente ou
  injoignable, plutôt que d'échouer bruyamment.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.database import check_connection, create_all  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def database_available() -> bool:
    if not settings.database_configured:
        return False
    ok, _ = check_connection()
    if ok:
        create_all()
    return ok


@pytest.fixture
def require_db(database_available: bool) -> None:
    if not database_available:
        pytest.skip(
            "Base de données indisponible : renseignez DATABASE_URL (Neon) dans backend/.env "
            "pour exécuter les tests d'intégration."
        )


@pytest.fixture
def temp_user(client: TestClient, require_db) -> dict:
    """Crée un compte apprenant jetable et renvoie son jeton + ses informations."""
    email = f"pytest-{uuid.uuid4().hex[:10]}@teachium-tests.ma"
    password = "MotDePasseTest123"
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Compte de test",
            "email": email,
            "password": password,
            "role": "learner",
            "course_category": "Python",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    data["password"] = password
    data["email"] = email
    yield data

    # Nettoyage : suppression via un administrateur si disponible, sinon on
    # laisse le compte inactif (les tests restent rejouables grâce à l'e-mail unique).
    admin = client.post(
        "/api/auth/login", json={"email": "admin@teachium.ma", "password": "Admin@2026"}
    )
    if admin.status_code == 200:
        token = admin.json()["access_token"]
        client.post(
            f"/api/admin/users/{data['user']['id']}/delete",
            headers={"Authorization": f"Bearer {token}"},
            json={"confirm_email": email},
        )


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
