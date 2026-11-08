from pathlib import Path
import joblib
import numpy as np
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
FEATURES = [
    "average_score",
    "time_spent_hours",
    "completion_rate",
    "quiz_attempts",
    "failed_quizzes",
    "login_frequency",
    "satisfaction_score",
]

_profile_model = None
_scaler = None
_cluster_model = None


def _load_artifacts():
    global _profile_model, _scaler, _cluster_model
    if _profile_model is None:
        classifier_path = MODEL_DIR / "profile_classifier.joblib"
        scaler_path = MODEL_DIR / "scaler.joblib"
        cluster_path = MODEL_DIR / "cluster_model.joblib"
        if classifier_path.exists():
            _profile_model = joblib.load(classifier_path)
        if scaler_path.exists():
            _scaler = joblib.load(scaler_path)
        if cluster_path.exists():
            _cluster_model = joblib.load(cluster_path)


def _risk_from_profile(profile: str) -> str:
    if profile in ["En difficulté", "Peu actif"]:
        return "Élevé"
    if profile in ["Débutant", "Moyen"]:
        return "Moyen"
    return "Faible"


def rule_based_profile(data: dict) -> str:
    """Fallback interprétable si les fichiers modèles ne sont pas encore générés."""
    score = data["average_score"]
    completion = data["completion_rate"]
    failed = data["failed_quizzes"]
    logins = data["login_frequency"]
    satisfaction = data.get("satisfaction_score") or 3.0

    if score >= 80 and completion >= 75 and failed <= 1:
        return "Avancé"
    if score < 50 and failed >= 3:
        return "En difficulté"
    if completion < 35 or logins <= 1 or satisfaction < 2.5:
        return "Peu actif"
    if score < 65:
        return "Débutant"
    return "Moyen"


def explain_profile(profile: str, data: dict) -> str:
    if profile == "Avancé":
        return "L'apprenant présente un score élevé, une bonne complétion et peu d'échecs aux quiz."
    if profile == "En difficulté":
        return "L'apprenant présente un score faible et plusieurs quiz échoués, ce qui indique un besoin de renforcement."
    if profile == "Peu actif":
        return "L'activité sur la plateforme ou le taux de complétion est faible, ce qui indique un risque de décrochage."
    if profile == "Débutant":
        return "L'apprenant possède des bases initiales mais nécessite encore un parcours guidé."
    return "L'apprenant présente des résultats moyens et peut progresser avec des exercices standards."


def analyze_profile(data: dict) -> dict:
    _load_artifacts()
    values = pd.DataFrame([[data.get(f, 0) for f in FEATURES]], columns=FEATURES, dtype=float)

    cluster = None
    if _profile_model is not None:
        profile = str(_profile_model.predict(values)[0])
    else:
        profile = rule_based_profile(data)

    if _scaler is not None and _cluster_model is not None:
        scaled = _scaler.transform(values)
        cluster = int(_cluster_model.predict(scaled)[0])

    return {
        "profile": profile,
        "cluster": cluster,
        "risk_level": _risk_from_profile(profile),
        "explanation": explain_profile(profile, data),
    }
