from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "app" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(42)
N = 350
courses = ["Python", "Data", "Web", "Management", "Communication"]
rows = []

for i in range(1, N + 1):
    profile_seed = np.random.choice(
        ["Avancé", "Moyen", "Débutant", "En difficulté", "Peu actif"],
        p=[0.18, 0.30, 0.20, 0.20, 0.12],
    )

    if profile_seed == "Avancé":
        score = np.random.normal(86, 7)
        completion = np.random.normal(88, 8)
        attempts = np.random.randint(6, 12)
        failed = np.random.randint(0, 2)
        logins = np.random.randint(4, 8)
        satisfaction = np.random.normal(4.4, 0.4)
        time_spent = np.random.normal(38, 8)
    elif profile_seed == "Moyen":
        score = np.random.normal(68, 8)
        completion = np.random.normal(65, 12)
        attempts = np.random.randint(4, 9)
        failed = np.random.randint(1, 3)
        logins = np.random.randint(3, 6)
        satisfaction = np.random.normal(3.6, 0.5)
        time_spent = np.random.normal(28, 8)
    elif profile_seed == "Débutant":
        score = np.random.normal(56, 9)
        completion = np.random.normal(55, 12)
        attempts = np.random.randint(3, 8)
        failed = np.random.randint(1, 4)
        logins = np.random.randint(2, 5)
        satisfaction = np.random.normal(3.2, 0.6)
        time_spent = np.random.normal(22, 7)
    elif profile_seed == "En difficulté":
        score = np.random.normal(39, 9)
        completion = np.random.normal(45, 15)
        attempts = np.random.randint(4, 10)
        failed = np.random.randint(3, 7)
        logins = np.random.randint(2, 5)
        satisfaction = np.random.normal(2.7, 0.7)
        time_spent = np.random.normal(30, 10)
    else:
        score = np.random.normal(50, 12)
        completion = np.random.normal(25, 10)
        attempts = np.random.randint(0, 5)
        failed = np.random.randint(0, 4)
        logins = np.random.randint(0, 2)
        satisfaction = np.random.normal(2.3, 0.6)
        time_spent = np.random.normal(10, 5)

    score = float(np.clip(score, 0, 100))
    completion = float(np.clip(completion, 0, 100))
    satisfaction = float(np.clip(satisfaction, 1, 5))
    total_courses = np.random.randint(6, 15)
    completed_courses = int(round(total_courses * completion / 100))

    rows.append({
        "student_id": f"STU{i:04d}",
        "course_category": np.random.choice(courses),
        "average_score": round(score, 2),
        "quiz_attempts": int(attempts),
        "completed_courses": int(completed_courses),
        "total_courses": int(total_courses),
        "time_spent_hours": round(float(max(time_spent, 0)), 2),
        "completion_rate": round(completion, 2),
        "login_frequency": int(logins),
        "failed_quizzes": int(failed),
        "satisfaction_score": round(satisfaction, 2),
        "true_profile": profile_seed,
    })

df = pd.DataFrame(rows)
out = DATA_DIR / "learners_dataset.csv"
df.to_csv(out, index=False, encoding="utf-8")
print(f"Dataset généré : {out}")
print(df.head())
