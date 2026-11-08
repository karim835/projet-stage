# TEACHIUM AI Tutor - Prototype MVP

Projet de stage : **Développement d'un système de tutorat intelligent basé sur l'IA pour la personnalisation des parcours d'apprentissage**.

Ce projet est un prototype complet à ouvrir dans **VS Code**. Il contient :

- un backend **FastAPI** ;
- un dataset apprenant simulé ;
- un modèle de profilage par **K-Means** ;
- un modèle de classification par **Decision Tree** ;
- un moteur de recommandation pédagogique ;
- un assistant conversationnel simple ;
- un dashboard **Streamlit** ;
- un rapport LaTeX complet.

## 1. Ouvrir le projet dans VS Code

```bash
cd teachium_ai_tutor_project
code .
```

## 2. Créer l'environnement Python

```bash
python -m venv .venv
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
source .venv/bin/activate
```

## 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

## 4. Générer les données

```bash
python scripts/generate_dataset.py
```

Résultat : `app/data/learners_dataset.csv`

## 5. Entraîner les modèles IA

```bash
python scripts/train_models.py
```

Résultats :

- `app/models/profile_classifier.joblib`
- `app/models/cluster_model.joblib`
- `app/models/scaler.joblib`
- `app/data/learners_with_profiles.csv`
- `app/data/model_metrics.json`
- graphiques dans `figures/`

## 6. Lancer l'API REST

```bash
uvicorn app.main:app --reload
```

Ensuite ouvre :

- API : http://127.0.0.1:8000
- Documentation Swagger : http://127.0.0.1:8000/docs

## 7. Tester les endpoints principaux

### Analyse de profil

`POST /api/profile/analyze`

```json
{
  "average_score": 45,
  "time_spent_hours": 12,
  "completion_rate": 40,
  "quiz_attempts": 5,
  "failed_quizzes": 3,
  "login_frequency": 2,
  "satisfaction_score": 2.5
}
```

### Recommandation

`POST /api/recommendations`

```json
{
  "profile": "En difficulté",
  "average_score": 45,
  "completion_rate": 40,
  "failed_quizzes": 3,
  "satisfaction_score": 2.5
}
```

### Chatbot

`POST /api/chatbot/ask`

```json
{
  "question": "Pourquoi cette ressource est recommandée ?",
  "profile": "En difficulté",
  "recommended_content": "Cours de révision + quiz de renforcement"
}
```

## 8. Lancer le dashboard Streamlit

Dans un deuxième terminal :

```bash
streamlit run dashboard/dashboard.py
```

## 9. Rapport LaTeX

Le rapport est dans :

```text
reports/rapport_stage_teachium.tex
```

Compilation recommandée :

```bash
cd reports
xelatex rapport_stage_teachium.tex
xelatex rapport_stage_teachium.tex
```

## Structure du projet

```text
teachium_ai_tutor_project/
├── app/
│   ├── main.py
│   ├── schemas/
│   ├── services/
│   ├── models/
│   └── data/
├── dashboard/
│   └── dashboard.py
├── scripts/
│   ├── generate_dataset.py
│   └── train_models.py
├── figures/
├── diagrams/
├── reports/
│   └── rapport_stage_teachium.tex
├── tests/
├── requirements.txt
└── README.md
```

## Remarque importante

Ce projet utilise des données simulées pour respecter la durée courte du stage et l'absence éventuelle de données réelles. Si TEACHIUM fournit des données réelles anonymisées, il suffit de remplacer `app/data/learners_dataset.csv` en gardant les mêmes colonnes principales.
