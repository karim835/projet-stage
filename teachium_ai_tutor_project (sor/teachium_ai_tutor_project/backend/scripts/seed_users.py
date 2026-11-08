"""Crée les comptes de démonstration (administrateur, formateur, apprenants).

    python scripts/seed_users.py [--reset-passwords]

Le script est idempotent : relancé, il ne crée aucun doublon.
Les comptes apprenants sont rattachés à de véritables lignes du dataset importé,
choisies pour illustrer trois profils différents. Aucune donnée n'est inventée :
les indicateurs affichés proviennent du CSV `learners_dataset.csv`.
"""

from __future__ import annotations

import argparse

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import check_connection, create_all, session_scope
from app.db.models import ROLE_ADMIN, ROLE_LEARNER, ROLE_TRAINER, Learner, User
from app.services import tutor_service

# Comptes de démonstration. Les mots de passe sont volontairement explicites :
# ce sont des comptes de démonstration, à changer avant toute mise en production.
DEMO_ACCOUNTS = [
    {
        "name": "Administrateur TEACHIUM",
        "email": "admin@teachium.ma",
        "password": "Admin@2026",
        "role": ROLE_ADMIN,
    },
    {
        "name": "Formateur TEACHIUM",
        "email": "formateur@teachium.ma",
        "password": "Formateur@2026",
        "role": ROLE_TRAINER,
    },
]

# (e-mail, nom affiché, profil de référence recherché dans le dataset)
DEMO_LEARNERS = [
    ("apprenant.difficulte@teachium.ma", "Apprenant Démo — En difficulté", "En difficulté"),
    ("apprenant.moyen@teachium.ma", "Apprenant Démo — Moyen", "Moyen"),
    ("apprenant.avance@teachium.ma", "Apprenant Démo — Avancé", "Avancé"),
]
DEMO_LEARNER_PASSWORD = "Apprenant@2026"


def _get_user(db, email: str) -> User | None:
    return db.execute(select(User).where(func.lower(User.email) == email.lower())).scalar_one_or_none()


def _next_student_id(db) -> str:
    last = db.execute(select(func.max(Learner.student_id))).scalar()
    if last and last.startswith("STU") and last[3:].isdigit():
        return f"STU{int(last[3:]) + 1:04d}"
    return "STU9001"


def _pick_learner(db, reference_profile: str) -> Learner | None:
    """Choisit un apprenant importé, sans compte, correspondant au profil visé."""
    return db.execute(
        select(Learner)
        .where(Learner.user_id.is_(None), Learner.reference_profile == reference_profile)
        .order_by(Learner.id)
        .limit(1)
    ).scalar_one_or_none()


def run(reset_passwords: bool = False) -> int:
    """Crée les comptes de démonstration. Réutilisable depuis init_database.py."""

    class _Args:
        pass

    args = _Args()
    args.reset_passwords = reset_passwords

    if not settings.database_configured:
        print("ERREUR : DATABASE_URL n'est pas définie (voir backend/.env.example).")
        return 2

    ok, message = check_connection()
    print(f"Connexion : {message}")
    if not ok:
        return 3

    create_all()

    with session_scope() as db:
        created: list[str] = []
        skipped: list[str] = []

        for account in DEMO_ACCOUNTS:
            user = _get_user(db, account["email"])
            if user is not None:
                if args.reset_passwords:
                    user.password_hash = hash_password(account["password"])
                    db.commit()
                    print(f"  ~ {account['email']} : mot de passe réinitialisé")
                else:
                    skipped.append(account["email"])
                continue
            db.add(
                User(
                    name=account["name"],
                    email=account["email"],
                    password_hash=hash_password(account["password"]),
                    role=account["role"],
                )
            )
            db.commit()
            created.append(account["email"])

        for email, name, reference_profile in DEMO_LEARNERS:
            user = _get_user(db, email)
            if user is not None:
                if args.reset_passwords:
                    user.password_hash = hash_password(DEMO_LEARNER_PASSWORD)
                    db.commit()
                    print(f"  ~ {email} : mot de passe réinitialisé")
                else:
                    skipped.append(email)
                continue

            user = User(
                name=name,
                email=email,
                password_hash=hash_password(DEMO_LEARNER_PASSWORD),
                role=ROLE_LEARNER,
            )
            db.add(user)
            db.flush()

            learner = _pick_learner(db, reference_profile)
            if learner is None:
                # Le dataset n'a pas été importé : on crée une fiche vierge.
                learner = Learner(user_id=user.id, student_id=_next_student_id(db))
                db.add(learner)
                print(f"  ! Aucun apprenant '{reference_profile}' disponible : fiche vierge créée pour {email}")
            else:
                learner.user_id = user.id

            db.commit()
            db.refresh(learner)

            if tutor_service.latest_profile(db, learner.id) is None:
                tutor_service.run_analysis(db, learner)

            created.append(f"{email} → {learner.student_id}")

        print()
        for item in created:
            print(f"  + créé : {item}")
        for item in skipped:
            print(f"  = existe déjà : {item}")

        print("\nComptes de démonstration :")
        print(f"  Administrateur : admin@teachium.ma / {DEMO_ACCOUNTS[0]['password']}")
        print(f"  Formateur      : formateur@teachium.ma / {DEMO_ACCOUNTS[1]['password']}")
        for email, _, profile in DEMO_LEARNERS:
            print(f"  Apprenant      : {email} / {DEMO_LEARNER_PASSWORD}   ({profile})")
        print("\nChangez ces mots de passe avant toute utilisation réelle.")

    return 0


def main_with_defaults() -> int:
    return run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Création des comptes de démonstration")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Réinitialiser les mots de passe des comptes de démonstration existants",
    )
    parsed = parser.parse_args()
    return run(reset_passwords=parsed.reset_passwords)


if __name__ == "__main__":
    sys.exit(main())
