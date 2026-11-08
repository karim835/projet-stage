from pathlib import Path
import sys
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# Les services IA vivent dans backend/ depuis la refonte web : on ajoute ce dossier
# au chemin d'import pour que `from app.services...` continue de fonctionner.
ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.profile_service import analyze_profile
from app.services.recommendation_service import recommend_content
from app.services.chatbot_service import chatbot_response

DATA_PATH = BACKEND_DIR / "app" / "data" / "learners_with_profiles.csv"
if not DATA_PATH.exists():
    DATA_PATH = BACKEND_DIR / "app" / "data" / "learners_dataset.csv"

st.set_page_config(page_title="TEACHIUM AI Tutor", layout="wide")
st.title("TEACHIUM AI Tutor - Dashboard")
st.caption(
    "Tableau de bord historique conservé pour l'expérimentation. "
    "L'interface principale de l'application est le frontend React (npm run dev sur http://localhost:5173)."
)
st.write("Prototype de système de tutorat intelligent pour la personnalisation des parcours d'apprentissage.")

@st.cache_data
def load_data():
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Aucune donnée disponible. Exécutez d'abord `python scripts/generate_dataset.py` puis `python scripts/train_models.py`.")
    st.stop()

profile_col = "true_profile" if "true_profile" in df.columns else "profile"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Apprenants", len(df))
col2.metric("Score moyen", f"{df['average_score'].mean():.1f}/100")
col3.metric("Complétion moyenne", f"{df['completion_rate'].mean():.1f}%")
col4.metric("Satisfaction moyenne", f"{df['satisfaction_score'].mean():.1f}/5")

st.subheader("Visualisation des données")
left, right = st.columns(2)

with left:
    st.write("Répartition des profils")
    counts = df[profile_col].value_counts()
    fig, ax = plt.subplots(figsize=(7, 4))
    counts.plot(kind="bar", ax=ax)
    ax.set_xlabel("Profil")
    ax.set_ylabel("Nombre")
    ax.set_title("Nombre d'apprenants par profil")
    st.pyplot(fig)

with right:
    st.write("Distribution des scores")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(df["average_score"], bins=20)
    ax.set_xlabel("Score moyen")
    ax.set_ylabel("Nombre")
    ax.set_title("Distribution des scores")
    st.pyplot(fig)

left2, right2 = st.columns(2)
with left2:
    st.write("Score moyen par profil")
    fig, ax = plt.subplots(figsize=(7, 4))
    df.groupby(profile_col)["average_score"].mean().sort_values().plot(kind="bar", ax=ax)
    ax.set_xlabel("Profil")
    ax.set_ylabel("Score moyen")
    st.pyplot(fig)

with right2:
    st.write("Relation temps passé / score")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(df["time_spent_hours"], df["average_score"], alpha=0.7)
    ax.set_xlabel("Temps passé (heures)")
    ax.set_ylabel("Score moyen")
    st.pyplot(fig)

st.subheader("Tester l'analyse d'un apprenant")
with st.form("learner_form"):
    c1, c2, c3 = st.columns(3)
    average_score = c1.slider("Score moyen", 0, 100, 55)
    completion_rate = c2.slider("Taux de complétion", 0, 100, 50)
    time_spent_hours = c3.slider("Temps passé (heures)", 0, 100, 20)
    c4, c5, c6 = st.columns(3)
    quiz_attempts = c4.slider("Quiz passés", 0, 20, 5)
    failed_quizzes = c5.slider("Quiz échoués", 0, 10, 2)
    login_frequency = c6.slider("Connexions / semaine", 0, 10, 3)
    satisfaction_score = st.slider("Satisfaction", 1.0, 5.0, 3.0, step=0.1)
    submitted = st.form_submit_button("Analyser")

if submitted:
    learner_data = {
        "average_score": average_score,
        "time_spent_hours": time_spent_hours,
        "completion_rate": completion_rate,
        "quiz_attempts": quiz_attempts,
        "failed_quizzes": failed_quizzes,
        "login_frequency": login_frequency,
        "satisfaction_score": satisfaction_score,
    }
    profile_result = analyze_profile(learner_data)
    rec_result = recommend_content(
        profile=profile_result["profile"],
        average_score=average_score,
        completion_rate=completion_rate,
        failed_quizzes=failed_quizzes,
        satisfaction_score=satisfaction_score,
    )
    st.success(f"Profil détecté : {profile_result['profile']} | Risque : {profile_result['risk_level']}")
    st.write(profile_result["explanation"])
    st.write("Recommandations :")
    for item in rec_result["recommended_content"]:
        st.write(f"- {item}")
    st.info(rec_result["reason"])

st.subheader("Assistant conversationnel")
question = st.text_input("Pose une question", "Pourquoi cette ressource est recommandée ?")
profile = st.selectbox("Profil", ["En difficulté", "Débutant", "Moyen", "Avancé", "Peu actif"])
if st.button("Répondre"):
    st.write(chatbot_response(question, profile, "Cours de révision"))
