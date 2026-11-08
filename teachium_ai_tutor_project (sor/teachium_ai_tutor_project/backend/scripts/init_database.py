"""Initialisation complète de la base Neon en une seule commande.

    python scripts/init_database.py

Étapes :
  1. vérification de DATABASE_URL et de la connexion à Neon ;
  2. création des tables (idempotent) ;
  3. import du dataset apprenants + exécution des modèles IA ;
  4. création des comptes de démonstration ;
  5. bibliothèque de cours et quiz de démonstration.

Chaque étape est rejouable : relancer la commande ne crée aucun doublon.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import inspect

from app.core.config import settings
from app.db.database import check_connection, create_all, get_engine


def step(number: int, title: str) -> None:
    print(f"\n[{number}/5] {title}")
    print("-" * 60)


def main() -> int:
    print("=" * 60)
    print("  TEACHIUM AI Tutor — initialisation de la base Neon")
    print("=" * 60)

    step(1, "Vérification de la connexion")
    if not settings.database_configured:
        print("ERREUR : DATABASE_URL n'est pas définie.")
        print()
        print("  1. Copiez backend/.env.example vers backend/.env")
        print("  2. Collez la chaîne de connexion fournie par la console Neon :")
        print("     DATABASE_URL=postgresql://<user>:<password>@<host>.neon.tech/<db>?sslmode=require")
        return 2

    print(f"Cible : {settings.safe_database_target()}")
    ok, message = check_connection()
    print(message)
    if not ok:
        print()
        print("Pistes de résolution :")
        print("  - vérifiez que la chaîne de connexion est complète et non expirée ;")
        print("  - vérifiez que votre projet Neon n'est pas supprimé ou suspendu ;")
        print("  - vérifiez votre connexion Internet (Neon est un service distant) ;")
        print("  - une instance Neon en veille peut mettre quelques secondes à démarrer : réessayez.")
        return 3

    step(2, "Création du schéma")
    create_all()
    tables = sorted(inspect(get_engine()).get_table_names())
    print(f"Tables présentes : {', '.join(tables)}")

    step(3, "Import du dataset et exécution des modèles IA")
    from scripts import import_dataset  # import tardif : le schéma doit exister

    code = import_dataset.main_with_defaults()
    if code != 0:
        return code

    step(4, "Comptes de démonstration")
    from scripts import seed_users

    code = seed_users.main_with_defaults()
    if code != 0:
        return code

    step(5, "Bibliothèque de cours et quiz de démonstration")
    from scripts import seed_content

    code = seed_content.main_with_defaults()
    if code != 0:
        return code

    print("\n" + "=" * 60)
    print("  Initialisation terminée.")
    print("  Lancez ensuite :  uvicorn app.main:app --reload")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
