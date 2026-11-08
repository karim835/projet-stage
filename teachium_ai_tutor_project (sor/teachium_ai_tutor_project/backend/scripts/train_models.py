from pathlib import Path
import json
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix

BASE_DIR = Path(__file__).resolve().parents[1]          # dossier backend/
PROJECT_DIR = BASE_DIR.parent                            # racine du projet
DATA_DIR = BASE_DIR / "app" / "data"
MODEL_DIR = BASE_DIR / "app" / "models"
FIG_DIR = PROJECT_DIR / "figures"                        # figures partagees avec le rapport LaTeX
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "average_score",
    "time_spent_hours",
    "completion_rate",
    "quiz_attempts",
    "failed_quizzes",
    "login_frequency",
    "satisfaction_score",
]

# 1. Chargement
dataset_path = DATA_DIR / "learners_dataset.csv"
if not dataset_path.exists():
    raise FileNotFoundError("Exécutez d'abord scripts/generate_dataset.py")

df = pd.read_csv(dataset_path)

# 2. Visualisations exploratoires
plt.figure(figsize=(8, 5))
plt.hist(df["average_score"], bins=20)
plt.title("Distribution des scores moyens")
plt.xlabel("Score moyen")
plt.ylabel("Nombre d'apprenants")
plt.tight_layout()
plt.savefig(FIG_DIR / "score_distribution.png", dpi=160)
plt.close()

plt.figure(figsize=(8, 5))
df["true_profile"].value_counts().plot(kind="bar")
plt.title("Répartition initiale des profils simulés")
plt.xlabel("Profil")
plt.ylabel("Nombre d'apprenants")
plt.tight_layout()
plt.savefig(FIG_DIR / "profiles_distribution.png", dpi=160)
plt.close()

plt.figure(figsize=(8, 5))
plt.scatter(df["time_spent_hours"], df["average_score"], alpha=0.7)
plt.title("Relation entre temps passé et score moyen")
plt.xlabel("Temps passé (heures)")
plt.ylabel("Score moyen")
plt.tight_layout()
plt.savefig(FIG_DIR / "score_vs_time.png", dpi=160)
plt.close()

# 3. Clustering K-Means
X = df[FEATURES]
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

inertias = []
ks = range(2, 9)
for k in ks:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X_scaled)
    inertias.append(km.inertia_)

plt.figure(figsize=(8, 5))
plt.plot(list(ks), inertias, marker="o")
plt.title("Méthode Elbow pour le choix du nombre de clusters")
plt.xlabel("Nombre de clusters k")
plt.ylabel("Inertie")
plt.tight_layout()
plt.savefig(FIG_DIR / "elbow_method.png", dpi=160)
plt.close()

kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_scaled)

# 4. Interprétation automatique simple des clusters
cluster_summary = df.groupby("cluster")[FEATURES].mean()

def name_cluster(row):
    if row["average_score"] >= 78 and row["completion_rate"] >= 70:
        return "Avancé"
    if row["average_score"] < 50 and row["failed_quizzes"] >= 3:
        return "En difficulté"
    if row["completion_rate"] < 40 or row["login_frequency"] <= 1:
        return "Peu actif"
    if row["average_score"] < 65:
        return "Débutant"
    return "Moyen"

cluster_names = {int(cluster): name_cluster(row) for cluster, row in cluster_summary.iterrows()}
df["profile"] = df["cluster"].map(cluster_names)

# Pour garantir des classes pédagogiques cohérentes avec le besoin, on garde true_profile comme cible pédagogique du modèle supervisé.
# La colonne profile représente l'interprétation du clustering, tandis que true_profile sert à entraîner le classificateur.

# 5. Classification supervisée avec arbre de décision
y = df["true_profile"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
clf = DecisionTreeClassifier(max_depth=5, random_state=42, class_weight="balanced")
clf.fit(X_train, y_train)
y_pred = clf.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted", zero_division=0)
report = classification_report(y_test, y_pred, zero_division=0, output_dict=True)
cm = confusion_matrix(y_test, y_pred, labels=clf.classes_)

# Confusion matrix simple
plt.figure(figsize=(8, 6))
plt.imshow(cm, interpolation="nearest")
plt.title("Matrice de confusion - Arbre de décision")
plt.xticks(range(len(clf.classes_)), clf.classes_, rotation=45, ha="right")
plt.yticks(range(len(clf.classes_)), clf.classes_)
plt.xlabel("Profil prédit")
plt.ylabel("Profil réel")
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        plt.text(j, i, str(cm[i, j]), ha="center", va="center")
plt.tight_layout()
plt.savefig(FIG_DIR / "confusion_matrix.png", dpi=160)
plt.close()

# Arbre de décision
plt.figure(figsize=(18, 10))
plot_tree(clf, feature_names=FEATURES, class_names=list(clf.classes_), filled=False, rounded=True, fontsize=8)
plt.title("Arbre de décision pour la classification des profils")
plt.tight_layout()
plt.savefig(FIG_DIR / "decision_tree.png", dpi=160)
plt.close()

# Completion by profile
plt.figure(figsize=(8, 5))
df.groupby("true_profile")["completion_rate"].mean().sort_values().plot(kind="bar")
plt.title("Taux de complétion moyen par profil")
plt.xlabel("Profil")
plt.ylabel("Taux de complétion moyen (%)")
plt.tight_layout()
plt.savefig(FIG_DIR / "completion_by_profile.png", dpi=160)
plt.close()

# 6. Sauvegardes
joblib.dump(clf, MODEL_DIR / "profile_classifier.joblib")
joblib.dump(kmeans, MODEL_DIR / "cluster_model.joblib")
joblib.dump(scaler, MODEL_DIR / "scaler.joblib")

df.to_csv(DATA_DIR / "learners_with_profiles.csv", index=False, encoding="utf-8")
cluster_summary.to_csv(DATA_DIR / "cluster_summary.csv", encoding="utf-8")

metrics = {
    "accuracy": round(float(accuracy), 4),
    "precision_weighted": round(float(precision), 4),
    "recall_weighted": round(float(recall), 4),
    "f1_weighted": round(float(f1), 4),
    "classes": list(clf.classes_),
    "classification_report": report,
    "cluster_names": cluster_names,
}
(DATA_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

# Recommandations test
recommendations = []
for _, row in df.head(50).iterrows():
    profile = row["true_profile"]
    if profile == "En difficulté":
        rec = "Cours de révision + quiz de renforcement"
        reason = "Score faible et plusieurs quiz échoués"
    elif profile == "Peu actif":
        rec = "Parcours court de reprise + rappel motivationnel"
        reason = "Taux de complétion ou fréquence de connexion faible"
    elif profile == "Avancé":
        rec = "Contenu avancé + mini-projet pratique"
        reason = "Score élevé et progression satisfaisante"
    elif profile == "Débutant":
        rec = "Module introductif + exercices guidés"
        reason = "Bases à consolider progressivement"
    else:
        rec = "Exercices standards + quiz de progression"
        reason = "Résultats moyens nécessitant de la pratique"
    recommendations.append({
        "student_id": row["student_id"],
        "profile": profile,
        "recommended_content": rec,
        "reason": reason,
    })
pd.DataFrame(recommendations).to_csv(DATA_DIR / "recommendations_test.csv", index=False, encoding="utf-8")

print("Modèles entraînés et sauvegardés.")
print(metrics)
