"""Importe le dataset apprenants CSV dans PostgreSQL (Neon).

    python scripts/import_dataset.py [--csv chemin.csv] [--no-analyze] [--limit N]

Comportement :

1. Lit `app/data/learners_dataset.csv` (le fichier d'origine n'est jamais modifié).
2. Valide chaque ligne (colonnes obligatoires, bornes des valeurs).
3. Insère ou met à jour les apprenants dans Neon — la clé `student_id` garantit
   l'absence de doublons, le script est donc rejouable sans risque.
4. Exécute la chaîne ML existante (K-Means + Decision Tree) sur chaque apprenant
   importé et enregistre profil + recommandations.
"""

from __future__ import annotations

import argparse

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.database import check_connection, create_all, session_scope
from app.db.models import Learner
from app.services import tutor_service

DEFAULT_CSV = BACKEND_DIR / "app" / "data" / "learners_dataset.csv"

REQUIRED_COLUMNS = [
    "student_id",
    "average_score",
    "completion_rate",
    "time_spent_hours",
    "quiz_attempts",
    "failed_quizzes",
    "login_frequency",
    "satisfaction_score",
]

BOUNDS = {
    "average_score": (0, 100),
    "completion_rate": (0, 100),
    "time_spent_hours": (0, 10000),
    "quiz_attempts": (0, 1000),
    "failed_quizzes": (0, 1000),
    "login_frequency": (0, 100),
    "satisfaction_score": (1, 5),
}


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Retourne (lignes valides, liste des problèmes rencontrés)."""
    problems: list[str] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes dans le CSV : {', '.join(missing)}")

    df = df.copy()
    df["student_id"] = df["student_id"].astype(str).str.strip()

    before = len(df)
    df = df[df["student_id"] != ""]
    if len(df) != before:
        problems.append(f"{before - len(df)} ligne(s) sans student_id ignorée(s)")

    before = len(df)
    df = df.drop_duplicates(subset=["student_id"], keep="first")
    if len(df) != before:
        problems.append(f"{before - len(df)} doublon(s) de student_id dans le CSV ignoré(s)")

    for column, (low, high) in BOUNDS.items():
        df[column] = pd.to_numeric(df[column], errors="coerce")
        invalid = df[column].isna() | (df[column] < low) | (df[column] > high)
        count = int(invalid.sum())
        if count:
            problems.append(f"{count} valeur(s) hors bornes ou non numériques dans '{column}' → corrigées")
            df.loc[df[column].isna(), column] = low
            df[column] = df[column].clip(low, high)

    return df, problems


def upsert_learners(db, df: pd.DataFrame) -> tuple[int, int]:
    """Insère les nouveaux apprenants, met à jour les existants. Renvoie (créés, mis à jour)."""
    existing = {
        row.student_id: row
        for row in db.execute(select(Learner).where(Learner.student_id.in_(df["student_id"].tolist()))).scalars()
    }

    created = updated = 0
    for record in df.to_dict(orient="records"):
        student_id = record["student_id"]
        values = {
            "course_category": (str(record.get("course_category")).strip() or None)
            if record.get("course_category") is not None and str(record.get("course_category")) != "nan"
            else None,
            "average_score": float(record["average_score"]),
            "completion_rate": float(record["completion_rate"]),
            "time_spent_hours": float(record["time_spent_hours"]),
            "quiz_attempts": int(record["quiz_attempts"]),
            "failed_quizzes": int(record["failed_quizzes"]),
            "login_frequency": int(record["login_frequency"]),
            "satisfaction_score": float(record["satisfaction_score"]),
            "completed_courses": int(record.get("completed_courses") or 0),
            "total_courses": int(record.get("total_courses") or 0),
            "reference_profile": (str(record["true_profile"]) if record.get("true_profile") else None),
        }

        learner = existing.get(student_id)
        if learner is None:
            db.add(Learner(student_id=student_id, **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(learner, key, value)
            updated += 1

    db.commit()
    return created, updated


def analyze_all(db, student_ids: list[str]) -> int:
    """Exécute la chaîne ML sur les apprenants sans profil enregistré."""
    learners = list(
        db.execute(select(Learner).where(Learner.student_id.in_(student_ids)).order_by(Learner.id)).scalars()
    )
    analysed = 0
    for learner in learners:
        if tutor_service.latest_profile(db, learner.id) is not None:
            continue
        tutor_service.run_analysis(db, learner)
        analysed += 1
        if analysed % 50 == 0:
            print(f"  ... {analysed} apprenants analysés")
    return analysed


def run(csv_path: Path = DEFAULT_CSV, analyze: bool = True, limit: int | None = None) -> int:
    """Exécute l'import. Réutilisable depuis scripts/init_database.py."""

    class _Args:
        csv = csv_path
        no_analyze = not analyze

    args = _Args()
    args.limit = limit

    if not settings.database_configured:
        print("ERREUR : DATABASE_URL n'est pas définie.")
        print("        Copiez backend/.env.example vers backend/.env et collez votre chaîne Neon.")
        return 2

    if not args.csv.exists():
        print(f"ERREUR : fichier introuvable : {args.csv}")
        print("        Générez-le avec : python scripts/generate_dataset.py")
        return 2

    print(f"Base cible      : {settings.safe_database_target()}")
    ok, message = check_connection()
    print(f"Connexion       : {message}")
    if not ok:
        return 3

    create_all()
    print("Schéma          : tables vérifiées / créées")

    df = pd.read_csv(args.csv)
    if args.limit:
        df = df.head(args.limit)
    df, problems = validate(df)
    print(f"Lignes valides  : {len(df)}")
    for problem in problems:
        print(f"  ! {problem}")

    try:
        with session_scope() as db:
            created, updated = upsert_learners(db, df)
            print(f"Apprenants      : {created} créé(s), {updated} mis à jour (aucun doublon)")

            if not args.no_analyze:
                print("Analyse ML      : exécution de K-Means + Arbre de décision...")
                analysed = analyze_all(db, df["student_id"].tolist())
                print(f"                  {analysed} nouveau(x) profil(s) enregistré(s)")
            else:
                print("Analyse ML      : ignorée (--no-analyze)")
    except SQLAlchemyError as exc:
        print(f"ERREUR base de données : {exc.__class__.__name__}")
        print("        Vérifiez DATABASE_URL et votre connexion Internet.")
        return 3

    print("\nImport terminé. Le fichier CSV d'origine n'a pas été modifié.")
    return 0


def main_with_defaults() -> int:
    return run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import du dataset apprenants vers Neon PostgreSQL")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Chemin du fichier CSV source")
    parser.add_argument("--no-analyze", action="store_true", help="Ne pas exécuter les modèles après import")
    parser.add_argument("--limit", type=int, default=None, help="N'importer que les N premières lignes")
    parsed = parser.parse_args()
    return run(csv_path=parsed.csv, analyze=not parsed.no_analyze, limit=parsed.limit)


if __name__ == "__main__":
    sys.exit(main())
