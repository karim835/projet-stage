"""Routes de statistiques : tableau de bord formateur et évaluation des modèles."""

from __future__ import annotations

from pathlib import Path as FsPath

from fastapi import APIRouter

from app.api.deps import DbSession, TrainerUser
from app.schemas.tutor import DashboardStats
from app.services import stats_service
from app.services.data_service import dashboard_stats as csv_dashboard_stats
from app.services.data_service import model_metrics
from app.services.profile_service import FEATURES, artifacts_status, get_classifier

router = APIRouter(tags=["Statistiques"])

FIGURES_DIR = FsPath(__file__).resolve().parents[4] / "figures"


@router.get(
    "/api/dashboard/stats",
    response_model=DashboardStats,
    summary="Indicateurs agrégés de la promotion",
)
def dashboard_stats(db: DbSession, _: TrainerUser):
    stats = stats_service.dashboard_stats_db(db)
    if stats["total_learners"] == 0:
        # Aucune donnée importée : on retombe sur le CSV du prototype initial
        # pour que le tableau de bord reste lisible, en le signalant clairement.
        csv_stats = csv_dashboard_stats()
        if "total_learners" in csv_stats:
            stats.update(
                {
                    "source": "csv_fallback",
                    "total_learners": csv_stats["total_learners"],
                    "average_score": csv_stats["average_score"],
                    "average_completion_rate": csv_stats["average_completion_rate"],
                    "average_satisfaction": csv_stats["average_satisfaction"],
                    "learners_by_profile": csv_stats["learners_by_profile"],
                    "risk_indicators": csv_stats["risk_indicators"],
                }
            )
    return stats


@router.get("/api/model/evaluate", summary="Métriques d'évaluation des modèles IA")
def evaluate(_: TrainerUser):
    """Métriques produites par scripts/train_models.py, enrichies d'informations
    lues directement sur les artefacts scikit-learn chargés en mémoire."""
    metrics = model_metrics()
    status = artifacts_status()

    clf = get_classifier()
    tree_info = None
    feature_importances = None
    if clf is not None:
        try:
            tree_info = {
                "type": type(clf).__name__,
                "max_depth": int(getattr(clf, "max_depth", 0) or 0),
                "effective_depth": int(clf.get_depth()),
                "n_leaves": int(clf.get_n_leaves()),
                "classes": [str(c) for c in clf.classes_],
            }
            importances = getattr(clf, "feature_importances_", None)
            if importances is not None:
                feature_importances = sorted(
                    (
                        {"feature": name, "importance": round(float(value), 4)}
                        for name, value in zip(FEATURES, importances)
                    ),
                    key=lambda item: item["importance"],
                    reverse=True,
                )
        except Exception:  # pragma: no cover - dépend de l'artefact chargé
            tree_info = None

    confusion = _confusion_matrix_from_report(metrics)

    return {
        **metrics,
        "artifacts": status,
        "decision_tree": tree_info,
        "feature_importances": feature_importances,
        "features": FEATURES,
        "confusion_matrix_figure_available": (FIGURES_DIR / "confusion_matrix.png").exists(),
        "confusion_matrix": confusion,
        "glossary": {
            "accuracy": "Pourcentage de prédictions correctes sur l'ensemble de test.",
            "precision": "Parmi les apprenants classés dans un profil, proportion réellement de ce profil.",
            "recall": "Parmi les apprenants réellement d'un profil, proportion correctement détectée.",
            "f1_score": "Moyenne harmonique de la précision et du rappel : un seul chiffre d'équilibre.",
            "support": "Nombre d'apprenants réels de ce profil dans l'échantillon de test.",
        },
    }


def _confusion_matrix_from_report(metrics: dict) -> dict | None:
    """La matrice de confusion complète n'est pas stockée dans model_metrics.json.

    On expose donc uniquement ce qui est réellement disponible : le support et le
    rappel par classe, qui donnent la diagonale (nombre de bonnes prédictions).
    L'image complète reste consultable dans figures/confusion_matrix.png.
    """
    report = metrics.get("classification_report")
    if not isinstance(report, dict):
        return None

    rows = []
    for label, values in report.items():
        if not isinstance(values, dict) or "support" not in values:
            continue
        if label in {"accuracy", "macro avg", "weighted avg"}:
            continue
        support = float(values.get("support") or 0)
        recall = float(values.get("recall") or 0)
        correct = round(support * recall)
        rows.append(
            {
                "profile": label,
                "support": int(support),
                "correct": int(correct),
                "incorrect": int(support - correct),
                "precision": round(float(values.get("precision") or 0), 4),
                "recall": round(recall, 4),
                "f1_score": round(float(values.get("f1-score") or 0), 4),
            }
        )
    if not rows:
        return None
    return {
        "note": (
            "Diagonale de la matrice de confusion reconstruite à partir du rapport de "
            "classification (support × rappel). La matrice complète est disponible dans "
            "figures/confusion_matrix.png."
        ),
        "rows": rows,
    }
