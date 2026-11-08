"""Statistiques agrégées calculées directement en base (Neon PostgreSQL).

Toutes les valeurs renvoyées ici proviennent de requêtes SQL réelles sur les
tables `learners`, `learner_profiles`, `recommendations` et `chat_messages`.
Aucune donnée n'est simulée côté API.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Learner, LearnerProfile, Recommendation, User

# Bornes des tranches de score utilisées par l'histogramme du frontend.
SCORE_BUCKETS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]


def _round(value, digits: int = 2):
    if value is None:
        return None
    return round(float(value), digits)


def latest_profile_subquery():
    """Sous-requête : identifiant du profil le plus récent de chaque apprenant."""
    return (
        select(
            LearnerProfile.learner_id.label("learner_id"),
            func.max(LearnerProfile.id).label("profile_id"),
        )
        .group_by(LearnerProfile.learner_id)
        .subquery()
    )


def current_profiles(db: Session) -> dict[int, LearnerProfile]:
    """Profil courant (le plus récent) de chaque apprenant, indexé par learner_id."""
    sub = latest_profile_subquery()
    rows = db.execute(
        select(LearnerProfile).join(sub, LearnerProfile.id == sub.c.profile_id)
    ).scalars()
    return {row.learner_id: row for row in rows}


def profile_distribution(db: Session) -> dict[str, int]:
    sub = latest_profile_subquery()
    rows = db.execute(
        select(LearnerProfile.profile, func.count(LearnerProfile.id))
        .join(sub, LearnerProfile.id == sub.c.profile_id)
        .group_by(LearnerProfile.profile)
        .order_by(func.count(LearnerProfile.id).desc())
    ).all()
    return {profile: int(count) for profile, count in rows}


def score_histogram(db: Session) -> list[dict]:
    buckets = []
    for low, high in SCORE_BUCKETS:
        count = db.execute(
            select(func.count(Learner.id)).where(
                Learner.average_score >= low, Learner.average_score < high
            )
        ).scalar_one()
        label = f"{low}-{high - 1}" if high <= 100 else f"{low}-100"
        buckets.append({"range": label, "count": int(count)})
    return buckets


def performance_by_profile(db: Session) -> list[dict]:
    """Score, complétion et satisfaction moyens pour chaque profil courant."""
    sub = latest_profile_subquery()
    rows = db.execute(
        select(
            LearnerProfile.profile,
            func.count(Learner.id),
            func.avg(Learner.average_score),
            func.avg(Learner.completion_rate),
            func.avg(Learner.satisfaction_score),
            func.avg(Learner.time_spent_hours),
        )
        .join(sub, LearnerProfile.id == sub.c.profile_id)
        .join(Learner, Learner.id == LearnerProfile.learner_id)
        .group_by(LearnerProfile.profile)
        .order_by(LearnerProfile.profile)
    ).all()
    return [
        {
            "profile": profile,
            "learners": int(count),
            "average_score": _round(avg_score, 1),
            "average_completion": _round(avg_completion, 1),
            "average_satisfaction": _round(avg_satisfaction, 2),
            "average_time_spent": _round(avg_time, 1),
        }
        for profile, count, avg_score, avg_completion, avg_satisfaction, avg_time in rows
    ]


def dashboard_stats_db(db: Session) -> dict:
    """Indicateurs principaux du tableau de bord formateur / administrateur."""
    totals = db.execute(
        select(
            func.count(Learner.id),
            func.avg(Learner.average_score),
            func.avg(Learner.completion_rate),
            func.avg(Learner.satisfaction_score),
            func.avg(Learner.time_spent_hours),
            func.sum(case((Learner.average_score < 50, 1), else_=0).cast(Integer)),
            func.sum(case((Learner.completion_rate < 40, 1), else_=0).cast(Integer)),
            func.sum(case((Learner.failed_quizzes >= 3, 1), else_=0).cast(Integer)),
            func.sum(case((Learner.login_frequency <= 1, 1), else_=0).cast(Integer)),
        )
    ).one()

    (
        total,
        avg_score,
        avg_completion,
        avg_satisfaction,
        avg_time,
        low_score,
        low_completion,
        many_failed,
        rarely_logged,
    ) = totals

    distribution = profile_distribution(db)

    return {
        "source": "database",
        "total_learners": int(total or 0),
        "average_score": _round(avg_score, 2),
        "average_completion_rate": _round(avg_completion, 2),
        "average_satisfaction": _round(avg_satisfaction, 2),
        "average_time_spent": _round(avg_time, 2),
        "learners_by_profile": distribution,
        "learners_in_difficulty": int(distribution.get("En difficulté", 0)),
        "inactive_learners": int(distribution.get("Peu actif", 0)),
        "advanced_learners": int(distribution.get("Avancé", 0)),
        "risk_indicators": {
            "low_score_count": int(low_score or 0),
            "low_completion_count": int(low_completion or 0),
            "high_failed_quizzes_count": int(many_failed or 0),
            "rarely_connected_count": int(rarely_logged or 0),
        },
        "score_histogram": score_histogram(db),
        "performance_by_profile": performance_by_profile(db),
    }


def admin_overview(db: Session) -> dict:
    """Vue système pour l'administrateur."""
    role_rows = db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all()
    users_by_role = {role: int(count) for role, count in role_rows}

    total_users = db.execute(select(func.count(User.id))).scalar_one()
    active_users = db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar_one()
    total_learners = db.execute(select(func.count(Learner.id))).scalar_one()
    linked_learners = db.execute(
        select(func.count(Learner.id)).where(Learner.user_id.is_not(None))
    ).scalar_one()
    total_profiles = db.execute(select(func.count(LearnerProfile.id))).scalar_one()
    total_recos = db.execute(select(func.count(Recommendation.id))).scalar_one()
    completed_recos = db.execute(
        select(func.count(Recommendation.id)).where(Recommendation.completed.is_(True))
    ).scalar_one()
    total_messages = db.execute(select(func.count(ChatMessage.id))).scalar_one()

    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    recent_analyses = db.execute(
        select(func.count(LearnerProfile.id)).where(LearnerProfile.created_at >= since)
    ).scalar_one()
    recent_messages = db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= since)
    ).scalar_one()

    return {
        "users_total": int(total_users or 0),
        "users_active": int(active_users or 0),
        "users_by_role": users_by_role,
        "learners_total": int(total_learners or 0),
        "learners_with_account": int(linked_learners or 0),
        "profiles_computed": int(total_profiles or 0),
        "recommendations_total": int(total_recos or 0),
        "recommendations_completed": int(completed_recos or 0),
        "chat_messages_total": int(total_messages or 0),
        "analyses_last_7_days": int(recent_analyses or 0),
        "messages_last_7_days": int(recent_messages or 0),
    }


def system_activity(db: Session, limit: int = 25) -> list[dict]:
    """Derniers événements réels du système (analyses, recommandations, messages)."""
    events: list[dict] = []

    profiles = db.execute(
        select(LearnerProfile, Learner.student_id)
        .join(Learner, Learner.id == LearnerProfile.learner_id)
        .order_by(LearnerProfile.created_at.desc(), LearnerProfile.id.desc())
        .limit(limit)
    ).all()
    for row, student_id in profiles:
        events.append(
            {
                "type": "profile_analysis",
                "label": f"Analyse de profil « {row.profile} »",
                "learner": student_id,
                "learner_id": row.learner_id,
                "created_at": row.created_at,
            }
        )

    messages = db.execute(
        select(ChatMessage, Learner.student_id)
        .join(Learner, Learner.id == ChatMessage.learner_id)
        .where(ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
    ).all()
    for row, student_id in messages:
        preview = row.message if len(row.message) <= 80 else row.message[:77] + "..."
        events.append(
            {
                "type": "chat_message",
                "label": f"Question à l'AI Tutor : « {preview} »",
                "learner": student_id,
                "learner_id": row.learner_id,
                "created_at": row.created_at,
            }
        )

    events.sort(key=lambda e: e["created_at"] or dt.datetime.min, reverse=True)
    return events[:limit]
