from pathlib import Path
import json
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_learners() -> pd.DataFrame:
    path = DATA_DIR / "learners_with_profiles.csv"
    if not path.exists():
        path = DATA_DIR / "learners_dataset.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def dashboard_stats() -> dict:
    df = load_learners()
    if df.empty:
        return {"message": "Aucune donnée disponible. Exécutez scripts/generate_dataset.py et scripts/train_models.py."}

    profile_col = "profile" if "profile" in df.columns else "true_profile"
    stats = {
        "total_learners": int(len(df)),
        "average_score": round(float(df["average_score"].mean()), 2),
        "average_completion_rate": round(float(df["completion_rate"].mean()), 2),
        "average_satisfaction": round(float(df["satisfaction_score"].mean()), 2),
        "learners_by_profile": df[profile_col].value_counts().to_dict(),
        "risk_indicators": {
            "low_score_count": int((df["average_score"] < 50).sum()),
            "low_completion_count": int((df["completion_rate"] < 40).sum()),
            "high_failed_quizzes_count": int((df["failed_quizzes"] >= 3).sum()),
        },
    }
    return stats


def model_metrics() -> dict:
    path = DATA_DIR / "model_metrics.json"
    if not path.exists():
        return {"message": "Métriques non disponibles. Entraînez les modèles d'abord."}
    return json.loads(path.read_text(encoding="utf-8"))
