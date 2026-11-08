# TEACHIUM AI Tutor

**Système de tutorat intelligent basé sur l'IA pour la personnalisation des parcours d'apprentissage.**

Application web complète : interface **React**, API **FastAPI**, modèles **scikit-learn**
(K-Means + arbre de décision) et base **PostgreSQL hébergée sur Neon**.

---

## Table des matières

1. [Objectif du projet](#1-objectif-du-projet)
2. [Architecture](#2-architecture)
3. [Technologies](#3-technologies)
4. [Prérequis](#4-prérequis)
5. [Configuration de la base Neon](#5-configuration-de-la-base-neon)
6. [Variables d'environnement](#6-variables-denvironnement)
7. [Installation et démarrage](#7-installation-et-démarrage)
8. [Comptes de démonstration](#8-comptes-de-démonstration)
9. [Base de données](#9-base-de-données)
10. [Import du dataset et contenus](#10-import-du-dataset-et-contenus)
11. [Modèles d'intelligence artificielle](#11-modèles-dintelligence-artificielle)
12. [Le système de quiz](#12-le-système-de-quiz)
13. [L'AI Tutor](#13-lai-tutor)
14. [Endpoints de l'API](#14-endpoints-de-lapi)
15. [Tests](#15-tests)
16. [Structure du projet](#16-structure-du-projet)
17. [Glossaire technique](#17-glossaire-technique)
18. [Limites connues](#18-limites-connues)

---

## 1. Objectif du projet

Le système permet de :

1. faire interagir un apprenant avec un tuteur intelligent ;
2. analyser les données d'apprentissage de chaque apprenant ;
3. déterminer automatiquement son **profil pédagogique** ;
4. générer des **recommandations personnalisées** ;
5. répondre aux questions de l'apprenant, sur son parcours comme sur le **contenu des cours** ;
6. permettre à un **formateur** de créer des **quiz**, de les attribuer et de suivre sa promotion ;
7. permettre à un **administrateur** de visualiser statistiques, comptes et métriques des modèles ;
8. persister toutes les données dans **PostgreSQL sur Neon** ;
9. réutiliser les modèles d'apprentissage automatique déjà entraînés dans le projet ;
10. guider l'apprenant de la **lecture d'une leçon** vers un **quiz existant pertinent**, puis vers
    des questions ciblées à poser à l'AI Tutor lorsqu'une notion n'est pas comprise.

---

## 2. Architecture

```text
┌──────────────────────────────┐
│   Frontend React + Vite      │   http://localhost:5173
│   Router · Axios · Recharts  │
└──────────────┬───────────────┘
               │ HTTP / REST (JSON + JWT)
               ▼
┌──────────────────────────────┐
│   Backend FastAPI            │   http://127.0.0.1:8000
│   ├── Authentification (JWT) │
│   ├── Gestion des apprenants │
│   ├── Analyse de profil      │
│   ├── Moteur de recommandation│
│   ├── AI Tutor / chatbot     │
│   ├── Statistiques           │
│   └── Services base de données│
└──────────────┬───────────────┘
               │ SQLAlchemy 2.0 + psycopg2 (TLS)
               ▼
┌──────────────────────────────┐
│   PostgreSQL — Neon (cloud)  │
└──────────────────────────────┘
```

### Chaîne de traitement IA

```text
Données apprenant  (7 variables)
        ↓
Prétraitement      (validation Pydantic + StandardScaler)
        ↓
K-Means (5 clusters)  ─────┐
        ↓                  │
Arbre de décision          │  →  Profil pédagogique + niveau de confiance
        ↓                  │
Profil retenu  ────────────┘
        ↓
Moteur de recommandation   →  Ressources + raison + priorité
        ↓
AI Tutor                   →  Explication personnalisée
        ↓
Persistance                →  Neon PostgreSQL
```

---

## 3. Technologies

| Couche | Technologies |
|---|---|
| Frontend | React 18, Vite 6, React Router 6, Axios, Recharts |
| Backend | FastAPI, Pydantic v2, Uvicorn |
| Base de données | PostgreSQL (Neon), SQLAlchemy 2.0, psycopg2-binary |
| Authentification | JWT (PyJWT), hachage bcrypt |
| Machine learning | scikit-learn 1.8, pandas, NumPy, joblib |
| Visualisation | Recharts (web), Matplotlib (figures du rapport) |
| Tests | Pytest, httpx |
| Historique | Streamlit (tableau de bord de référence, optionnel) |

---

## 4. Prérequis

- **Python 3.11 ou plus récent**
- **Node.js 18 ou plus récent** (npm inclus)
- Une **connexion Internet** (la base est hébergée chez Neon)
- Un compte **Neon** gratuit : <https://neon.tech>

> **Aucune installation de PostgreSQL n'est nécessaire.**
> Pas de serveur local, pas de pgAdmin, pas de service Windows, pas de `localhost:5432`.
> L'application ouvre une connexion réseau chiffrée vers votre instance Neon.

---

## 5. Configuration de la base Neon

1. Créez un compte gratuit sur <https://neon.tech>.
2. Cliquez sur **New Project**, donnez-lui un nom (par exemple `teachium`) et choisissez
   la région la plus proche.
3. Neon crée automatiquement une base nommée `neondb`. Aucune commande SQL n'est à taper :
   les tables sont créées par le script d'initialisation.
4. Ouvrez **Connection Details** (ou **Connect**) sur le tableau de bord du projet et copiez la
   chaîne de connexion. Elle ressemble à :

   ```text
   postgresql://neondb_owner:MOT_DE_PASSE@ep-xxxx-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

5. Copiez `backend/.env.example` vers `backend/.env` et collez la chaîne dans `DATABASE_URL`.
6. Générez une clé JWT et collez-la dans `JWT_SECRET` :

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

7. Lancez l'initialisation (voir [§7](#7-installation-et-démarrage)) :

   ```bash
   python scripts/init_database.py
   ```

   Cette commande crée les tables, importe les 350 apprenants du dataset, exécute les modèles
   sur chacun d'eux et crée les comptes de démonstration.

**Notes utiles sur Neon**

- Une instance gratuite se met en veille après quelques minutes d'inactivité. La première
  requête après une veille peut prendre 2 à 5 secondes : c'est normal. Le délai de connexion
  est réglé à 20 secondes et le pool vérifie chaque connexion avant usage (`pool_pre_ping`).
- Le paramètre `channel_binding=require` que propose la console Neon est automatiquement retiré
  de l'URL : il n'est pas accepté par toutes les versions de libpq et n'est pas nécessaire,
  le chiffrement étant déjà assuré par `sslmode=require`.
- Le préfixe historique `postgres://` est converti automatiquement en `postgresql+psycopg2://`.

---

## 6. Variables d'environnement

Fichier `backend/.env` (jamais commité — voir `.gitignore`) :

| Variable | Obligatoire | Rôle |
|---|---|---|
| `DATABASE_URL` | **oui** | Chaîne de connexion Neon |
| `JWT_SECRET` | fortement recommandé | Clé de signature des jetons. Si absente, une clé éphémère est générée et **toutes les sessions sont invalidées à chaque redémarrage**. |
| `JWT_ALGORITHM` | non | `HS256` par défaut |
| `JWT_EXPIRE_MINUTES` | non | Durée de validité des sessions (720 min par défaut) |
| `CORS_ORIGINS` | non | Origines autorisées, séparées par des virgules |
| `LLM_API_KEY` / `LLM_MODEL` | non | Réservées à une intégration LLM future. **Non requises** : l'AI Tutor actuel ne les utilise pas. |
| `SQL_ECHO` | non | `true` pour afficher les requêtes SQL |

Côté frontend, `frontend/.env` n'accepte que `VITE_API_URL`. **Aucun secret ne doit y figurer** :
toute variable `VITE_*` est intégrée en clair dans le bundle JavaScript public.

---

## 7. Installation et démarrage

### Backend

```bash
cd backend
python -m venv .venv
```

Windows (PowerShell) :

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows (invite de commandes) :

```bat
.\.venv\Scripts\activate
```

Linux / macOS :

```bash
source .venv/bin/activate
```

Puis :

```bash
pip install -r requirements.txt
copy .env.example .env          REM Windows   (cp .env.example .env sous Linux/macOS)
REM ... collez votre DATABASE_URL Neon dans .env ...
python scripts/init_database.py
uvicorn app.main:app --reload
```

Après une mise à jour du projet, relancez `python scripts/init_database.py` une fois avant le
backend. La commande est idempotente : elle conserve les données Neon existantes et crée les
champs/tables manquants, notamment le suivi des leçons terminées.

L'API est disponible sur :

- <http://127.0.0.1:8000>
- Documentation Swagger : <http://127.0.0.1:8000/docs>
- État de santé : <http://127.0.0.1:8000/health>

### Frontend

Dans un **second terminal** :

```bash
cd frontend
npm install
npm run dev
```

L'interface est disponible sur <http://localhost:5173>.

### Raccourcis Windows

À la racine du projet :

| Script | Rôle |
|---|---|
| `setup_backend.bat` | venv + dépendances + initialisation de la base Neon |
| `run_backend.bat` | démarre l'API FastAPI |
| `run_frontend.bat` | installe (si besoin) et démarre l'interface React |
| `run_dashboard_streamlit.bat` | tableau de bord Streamlit historique (optionnel) |

Équivalents Linux / macOS : `setup_backend.sh`, `run_backend.sh`, `run_frontend.sh`.

---

## 8. Comptes de démonstration

Créés par `scripts/seed_users.py` (appelé automatiquement par `init_database.py`).
Les comptes apprenants sont rattachés à de **vraies lignes du dataset**, choisies pour illustrer
trois profils différents.

| Rôle | Adresse e-mail | Mot de passe | Profil |
|---|---|---|---|
| Administrateur | `admin@teachium.ma` | `Admin@2026` | — |
| Formateur | `formateur@teachium.ma` | `Formateur@2026` | — |
| Apprenant | `apprenant.difficulte@teachium.ma` | `Apprenant@2026` | En difficulté |
| Apprenant | `apprenant.moyen@teachium.ma` | `Apprenant@2026` | Moyen |
| Apprenant | `apprenant.avance@teachium.ma` | `Apprenant@2026` | Avancé |

La page de connexion propose un bouton par compte de démonstration : un clic connecte directement.

> Ces mots de passe sont volontairement lisibles pour la démonstration.
> Changez-les avant toute utilisation réelle (`python scripts/seed_users.py --reset-passwords`
> après avoir modifié les valeurs dans le script, ou via l'interface).

Après connexion, la redirection est automatique selon le rôle :

| Rôle | Page d'accueil |
|---|---|
| `learner` | `/apprenant` |
| `trainer` | `/formateur` |
| `administrator` | `/admin` |

---

## 9. Base de données

Douze tables, créées automatiquement par `create_all()` (SQLAlchemy) :

| Table | Contenu |
|---|---|
| `users` | Comptes : nom, e-mail unique, empreinte bcrypt, rôle, état actif |
| `learners` | Fiche apprenant : les 7 variables des modèles + cours suivis + profil de référence |
| `learner_profiles` | Résultat horodaté de chaque analyse : profil, cluster, confiance, risque, explication, source |
| `recommendations` | Ressource recommandée, raison, priorité, état « suivie » |
| `learning_activity` | Quiz passés, cours terminés, sessions de travail |
| `chat_messages` | Historique de conversation avec l'AI Tutor (`user` / `assistant`) |
| `quizzes` | Quiz créé par un formateur : titre, filière, difficulté, note de réussite, publication, lien facultatif vers une fiche |
| `quiz_questions` | Question à choix unique : énoncé, propositions (JSON), **index de la bonne réponse**, indice sûr, notion et explication |
| `quiz_assignments` | Attribution d'un quiz à un apprenant (unique par couple quiz/apprenant) |
| `quiz_attempts` | Copie corrigée : note calculée, détail des réponses, durée mesurée, réussite |
| `course_resources` | Fiches de cours — base de connaissances interrogée par l'AI Tutor |
| `course_completions` | Confirmation qu'un apprenant a terminé une fiche et quiz existant recommandé |

**Relations** — `users 1—0..1 learners` ; `learners 1—N learner_profiles`,
`1—N recommendations`, `1—N learning_activity`, `1—N chat_messages` et
`1—N course_completions`. Les données possédées par un apprenant sont supprimées en cascade ;
les références facultatives comme le créateur d'un quiz ou le quiz conseillé utilisent
`ON DELETE SET NULL` afin de conserver l'historique pertinent.

**Index** — sur `users.email`, `users.role`, `learners.student_id`, `learners.user_id`,
`learners.course_category`, le couple `(average_score, completion_rate)`, et sur
`(learner_id, created_at)` pour les profils, recommandations, activités et messages.

**Contraintes** — rôle limité aux trois valeurs autorisées, score et complétion bornés entre
0 et 100, rôle de message limité à `user` / `assistant`.

`quiz_questions.correct_index` n'est **jamais** transmis à un apprenant avant qu'il n'ait rendu
sa copie : l'endpoint de passage renvoie un schéma restreint qui ne contient pas ce champ.

`learners.user_id` est volontairement **nullable** : les 350 apprenants importés du dataset
sont anonymisés et n'ont pas tous de compte de connexion.

---

## 10. Import du dataset et contenus

```bash
cd backend
python scripts/import_dataset.py
```

Options : `--csv <chemin>`, `--limit N`, `--no-analyze`.

Le script :

1. lit `app/data/learners_dataset.csv` — **le fichier d'origine n'est jamais modifié** ;
2. valide chaque ligne (colonnes obligatoires, bornes, doublons de `student_id`) et signale
   les corrections appliquées ;
3. insère ou met à jour les apprenants dans Neon. La clé `student_id` garantit l'absence de
   doublons : **le script est rejouable sans risque** ;
4. exécute la chaîne ML complète sur chaque apprenant nouvellement importé et enregistre
   profil + recommandations.

Le format CSV attendu reste celui du prototype d'origine, ce qui permet de continuer à utiliser
`scripts/generate_dataset.py` et `scripts/train_models.py` sans modification.

### Bibliothèque de cours et quiz de démonstration

```bash
python scripts/seed_content.py          # ajoute les fiches et quiz manquants
python scripts/seed_content.py --reset  # les supprime puis les recrée
```

Le script insère 15 fiches de cours réparties en 5 filières (Python, Data, Web, Management,
Communication) et 5 quiz publiés, puis attribue à chaque apprenant disposant d'un compte les quiz
de sa filière. Il est idempotent : relancé, il ne crée aucun doublon.

### Régénérer les données et réentraîner les modèles

```bash
python scripts/generate_dataset.py    # régénère le CSV simulé (350 apprenants)
python scripts/train_models.py        # réentraîne K-Means + arbre, régénère figures et métriques
python scripts/generate_diagrams.py   # régénère les diagrammes du rapport
```

---

## 11. Modèles d'intelligence artificielle

Les artefacts entraînés sont conservés tels quels dans `backend/app/models/` :

| Fichier | Modèle |
|---|---|
| `scaler.joblib` | `StandardScaler` — normalisation des 7 variables |
| `cluster_model.joblib` | `KMeans(n_clusters=5)` — regroupement non supervisé |
| `profile_classifier.joblib` | `DecisionTreeClassifier(max_depth=5, class_weight="balanced")` |

### Les 7 variables d'entrée

`average_score`, `time_spent_hours`, `completion_rate`, `quiz_attempts`,
`failed_quizzes`, `login_frequency`, `satisfaction_score`.

### K-Means

Apprentissage **non supervisé**. Il regroupe les apprenants en 5 groupes homogènes sans
connaître les profils à l'avance, en minimisant la distance de chaque apprenant au centre de
son groupe. Les variables sont d'abord normalisées par le `StandardScaler`, sinon une variable
à grande échelle (le temps passé) écraserait une variable à petite échelle (la satisfaction).
Le nombre de groupes a été choisi par la **méthode du coude** (`figures/elbow_method.png`).
Le cluster obtenu est affiché dans l'interface comme information complémentaire.

### Arbre de décision

Apprentissage **supervisé**. Il apprend une suite de questions simples
(« le score est-il inférieur à 50 ? », « y a-t-il plus de 2 quiz échoués ? ») menant à l'un des
cinq profils : **Avancé, Moyen, Débutant, En difficulté, Peu actif**. C'est ce modèle qui
détermine le profil affiché. Son grand avantage ici est la **lisibilité** : le chemin de
décision est explicable à un formateur, ce qui compte pour un outil pédagogique.

L'API expose aussi la **confiance** de la prédiction (`predict_proba` de la classe retenue) et
l'**importance des variables** (`feature_importances_`), toutes deux lues sur le modèle chargé
en mémoire — donc réelles, jamais recopiées d'un fichier figé.

### Moteur de recommandation

Système de règles pédagogiques (`app/services/recommendation_service.py`) : à chaque profil
correspond un jeu de ressources, complété par des ajustements liés aux indicateurs
(complétion inférieure à 40 %, au moins 3 quiz échoués, satisfaction inférieure à 2,5).
Chaque recommandation est accompagnée d'une **raison** et d'une **priorité**.

### Repli interprétable

Si les fichiers `.joblib` sont absents, `profile_service.rule_based_profile()` prend le relais
avec des règles explicites. L'API indique alors `source: "rules"` au lieu de `source: "model"`,
et l'interface affiche la différence. Il n'y a donc jamais de résultat silencieusement dégradé.

### Évaluation

Métriques produites par `scripts/train_models.py`, stockées dans `app/data/model_metrics.json`
et affichées sur la page **Évaluation du modèle** :

| Indicateur | Valeur | Signification en langage simple |
|---|---|---|
| Exactitude (accuracy) | 84,1 % | Pourcentage de prédictions correctes |
| Précision pondérée | 86,1 % | Quand un profil est annoncé, à quelle fréquence est-ce le bon |
| Rappel pondéré | 84,1 % | Parmi les apprenants d'un profil, combien sont détectés |
| F1-score pondéré | 84,6 % | Équilibre entre précision et rappel |

La matrice de confusion complète est disponible dans `figures/confusion_matrix.png`.
L'interface en reconstruit la diagonale (bien classés / mal classés par profil) à partir du
rapport de classification.

---

## 12. Le système de quiz

### Principe

**Un apprenant ne peut jamais s'attribuer une note.** C'est la règle structurante de cette partie,
appliquée à tous les niveaux :

* l'apprenant ne transmet que des **index de réponses** ; le champ `score` éventuellement envoyé
  dans la requête est purement et simplement ignoré par le serveur ;
* la bonne réponse (`correct_index`) n'est **pas envoyée** avant la soumission de la copie ;
* la route de saisie libre d'une note par l'apprenant a été supprimée (`405 Method Not Allowed`) ;
* la saisie d'une évaluation hors ligne est réservée au rôle formateur (`403` pour un apprenant).

### Côté formateur / administrateur

Depuis **Quiz** :

1. **créer un quiz** — titre, filière, difficulté, note de réussite, puis les questions
   (2 à 6 propositions par question, une seule bonne réponse, indice facultatif qui ne révèle
   pas la réponse, puis explication affichée après correction) ;
2. **publier ou dépublier** — un quiz non publié est invisible et ne peut pas être attribué ;
3. **attribuer** à un ou plusieurs apprenants (opération idempotente) ;
4. **consulter les résultats** : moyenne, taux de réussite, tableau par apprenant, et
   **taux de réussite question par question** — les questions les plus manquées apparaissent en
   premier, ce qui identifie les notions à retravailler avec le groupe.

Depuis la **fiche d'un apprenant**, le bouton **« Saisir une évaluation »** enregistre la note
d'un devoir ou d'un examen en présentiel. C'est la seule autre source de notes du système.

### Côté apprenant

Depuis **Mes quiz** : la liste des quiz attribués ou ouverts à sa filière, ceux déjà réussis, et
l'historique de ses copies. Il passe le quiz dans l'interface, envoie sa copie, et reçoit
immédiatement :

* sa note calculée par le serveur ;
* la correction question par question, avec la bonne réponse et l'explication ;
* l'effet réel sur ses indicateurs et, le cas échéant, son changement de profil ;
* un bilan pédagogique ciblé et des **questions prêtes à poser à l'AI Tutor** à partir des erreurs.

Pendant un quiz, l'apprenant peut demander un indice progressif. Cet indice est produit ou validé
côté serveur et ne contient jamais la bonne réponse ni l'explication de correction.

### Parcours leçon → quiz → AI Tutor

Dans la bibliothèque, l'apprenant ouvre une fiche, la lit puis confirme **« J'ai terminé cette
leçon »**. Cette confirmation est idempotente : plusieurs clics ne créent ni doublon ni activité
supplémentaire. Le serveur propose alors le quiz publié existant le plus pertinent : lien explicite
avec la fiche lorsqu'il existe, sinon rapprochement par filière, titre, mots-clés et notions. Aucun
quiz et aucune leçon ne sont générés automatiquement.

Après une réponse incorrecte, la correction transforme les notions à revoir en formulations
concrètes. Un clic ouvre l'AI Tutor avec la question déjà préparée dans le champ de saisie, afin que
l'apprenant puisse demander une explication avant de refaire le quiz.

### Effet sur les indicateurs

Après correction, le serveur met à jour la fiche apprenant puis **relance les modèles** :

* `quiz_attempts + 1` ; `failed_quizzes + 1` si la note est sous le seuil de réussite ;
* moyenne recalculée de façon incrémentale :
  `(moyenne × tentatives + note) / (tentatives + 1)` ;
* `time_spent_hours` augmenté de la **durée réellement mesurée** entre l'ouverture et l'envoi de
  la copie (plafonnée à 4 heures pour qu'une copie oubliée ne fausse pas l'indicateur).

Un quiz reste une évaluation : son attribution ou sa réussite ne modifie plus artificiellement le
nombre de cours terminés. La progression dans la bibliothèque est enregistrée séparément dans
`course_completions`, au moment où l'apprenant confirme avoir fini une leçon.

Le profil pédagogique et les recommandations sont donc réellement recalculés à partir d'une note
que l'apprenant n'a pas pu choisir.

---

## 13. L'AI Tutor

**Le tuteur n'est pas un grand modèle de langage, et l'application ne le prétend jamais.**
L'API renvoie explicitement `engine: "rules"` et l'interface affiche la mention correspondante.

Il combine trois mécanismes.

### 1. Reconnaissance d'intention

Une vingtaine d'intentions pédagogiques, chacune décrite par des expressions déclenchantes
pondérées : profil, explication du calcul du profil, score, complétion, temps, résultats de quiz,
quiz à passer, points faibles, recommandations, conseils de progression, cours à revoir, méthode
de travail, découragement, comparaison avec la promotion, fonctionnement des algorithmes,
catalogue de cours, prochaine étape, satisfaction, salutations, aide.

Le texte de la question et les expressions sont normalisés de la même façon : minuscules, accents
supprimés, apostrophes et traits d'union remplacés par des espaces. « Quels quiz dois-je passer ? »
et « quiz dois je passer » sont donc reconnus à l'identique.

### 2. Ancrage dans les données réelles

Chaque réponse cite les chiffres lus en base pour cet apprenant : score, complétion, quiz échoués,
connexions, cluster K-Means, confiance du modèle, recommandations en cours et leur raison,
résultats de quiz par filière, et **les questions précisément manquées** lors des quiz — ce qui
permet de désigner les notions à revoir plutôt que de donner un conseil générique.

### 3. Recherche documentaire TF-IDF

Pour toute question portant sur le contenu d'un cours, le tuteur interroge la **bibliothèque de
cours** (table `course_resources`).

* Chaque fiche est transformée en vecteur de poids de mots (`TfidfVectorizer` de scikit-learn,
  unigrammes et bigrammes), la question est projetée dans le même espace, et la proximité est
  mesurée par similarité cosinus.
* Le français est traité par un tokeniseur dédié : accents supprimés, liste de mots vides
  française, et racinisation légère des pluriels (« boucles » et « boucle » sont assimilés).
* Une fiche de la filière de l'apprenant reçoit un bonus modéré (×1,3) appliqué **au score**, et
  non un tri par catégorie : une fiche hors filière nettement plus pertinente reste devant.
* Le tuteur ne renvoie pas la fiche entière mais le **paragraphe le plus proche** de la question,
  et **cite toujours la fiche source**, ce qui permet de vérifier l'origine de la réponse.
* En dessous d'un seuil de similarité, le tuteur **dit qu'il ne sait pas** et propose de
  reformuler, plutôt que d'inventer une réponse.

Exemples réellement traités : « C'est quoi une boucle for en Python ? », « À quoi sert la
normalisation avant K-Means ? », « Quelle est la différence entre 401 et 403 ? »,
« Qui priorise le backlog dans Scrum ? », « Comment réussir ma soutenance orale ? ».

### Gestion des conflits entre les deux sources

Une question de conseil (« comment progresser », « quoi réviser », « comment m'organiser ») pour
laquelle la bibliothèque possède une fiche nettement pertinente reçoit la fiche plutôt qu'un
conseil générique. « Comment réussir ma soutenance orale ? » renvoie donc la fiche sur la
présentation orale, et non un conseil sur la progression.

### Brancher un vrai LLM plus tard

L'architecture est prête (`app/services/tutor_service.py`) :

```python
class LLMTutorEngine(TutorEngine):
    name = "llm"
    label = "Modèle de langage <fournisseur>"

    def answer(self, question: str, context: TutorContext) -> str:
        ...  # appel à l'API du fournisseur, en injectant `context`

register_engine(LLMTutorEngine())
```

`get_engine()` sélectionne alors automatiquement ce moteur dès que `LLM_API_KEY` est définie.
Aucune autre partie de l'application n'a besoin d'être modifiée. Tant qu'aucune implémentation
n'est enregistrée, la clé reste inutile et n'est pas requise.

---

## 14. Endpoints de l'API

Documentation interactive complète : <http://127.0.0.1:8000/docs>

### Système

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/` | public | Racine de l'API |
| GET | `/health` | public | État base de données + modèles + moteur du tuteur |

### Authentification

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| POST | `/api/auth/register` | public | Créer un compte (201) |
| POST | `/api/auth/login` | public | Obtenir un jeton JWT |
| GET | `/api/auth/me` | connecté | Compte courant |
| POST | `/api/auth/change-password` | connecté | Changer son mot de passe |

### Modèles IA — sans état (endpoints d'origine, conservés)

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| POST | `/api/profile/analyze` | public | Analyse de profil (K-Means + arbre) |
| POST | `/api/recommendations` | public | Génération de recommandations |
| POST | `/api/chatbot/ask` | public | Question au tuteur, sans contexte |
| GET | `/api/tutor/engine` | public | Nature du moteur conversationnel |

### Apprenant

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/learners/me` | apprenant | Tableau de bord complet |
| PATCH | `/api/learners/me` | apprenant | Mettre à jour ses indicateurs |
| POST | `/api/learners/me/analyze` | apprenant | Relancer l'analyse ML |
| GET | `/api/learners/me/activity` | apprenant | Historique d'activité |
| GET | `/api/recommendations/me` | apprenant | Recommandations en cours |
| GET | `/api/recommendations/me/history` | apprenant | Historique complet |
| POST | `/api/recommendations/{id}/complete` | apprenant | Marquer comme suivie |
| POST | `/api/chat/ask` | apprenant | Question à l'AI Tutor (persistée) |
| GET | `/api/chat/history` | apprenant | Historique de conversation |
| DELETE | `/api/chat/history` | apprenant | Effacer la conversation |

### Quiz — apprenant

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/quizzes/me` | apprenant | Quiz attribués ou ouverts à sa filière |
| GET | `/api/quizzes/me/attempts` | apprenant | Historique de ses copies |
| GET | `/api/quizzes/{id}/take` | apprenant | Ouvrir un quiz — **sans les bonnes réponses** |
| GET | `/api/quizzes/{id}/questions/{question_id}/hint` | apprenant | Obtenir un indice sans divulguer la correction |
| POST | `/api/quizzes/{id}/submit` | apprenant | Envoyer sa copie ; correction serveur (201) |
| GET | `/api/quizzes/attempts/{id}` | apprenant | Revoir la correction d'une copie |

### Quiz — formateur et administrateur

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/quizzes` | formateur | Lister les quiz |
| POST | `/api/quizzes` | formateur | Créer un quiz avec ses questions (201) |
| GET | `/api/quizzes/{id}` | formateur | Détail complet, bonnes réponses incluses |
| PATCH | `/api/quizzes/{id}` | formateur | Modifier (questions verrouillées après un passage) |
| DELETE | `/api/quizzes/{id}` | formateur | Supprimer le quiz et ses copies |
| POST | `/api/quizzes/{id}/assign` | formateur | Attribuer à des apprenants |
| DELETE | `/api/quizzes/{id}/assign/{learner_id}` | formateur | Retirer une attribution |
| GET | `/api/quizzes/{id}/results` | formateur | Résultats + réussite par question |
| POST | `/api/learners/{id}/evaluations` | formateur | Saisir la note d'une évaluation hors ligne (201) |

### Bibliothèque de cours

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/courses` | connecté | Lister les fiches |
| GET | `/api/courses/categories` | connecté | Filières et effectifs |
| GET | `/api/courses/search` | connecté | Recherche par pertinence (TF-IDF) |
| GET | `/api/courses/{id}` | connecté | Lire une fiche complète |
| POST | `/api/courses/{id}/complete` | apprenant | Confirmer la leçon et recevoir un quiz existant pertinent |
| POST | `/api/courses` | formateur | Créer une fiche (201) |
| PATCH | `/api/courses/{id}` | formateur | Modifier une fiche |
| DELETE | `/api/courses/{id}` | formateur | Supprimer une fiche |

### Formateur (et administrateur)

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/learners` | formateur | Liste filtrable, triable, paginée |
| GET | `/api/learners/{id}` | formateur | Fiche détaillée |
| PATCH | `/api/learners/{id}` | formateur | Modifier les indicateurs |
| POST | `/api/learners/{id}/analyze` | formateur | Relancer l'analyse |
| GET | `/api/dashboard/stats` | formateur | Statistiques agrégées |
| GET | `/api/model/evaluate` | formateur | Métriques des modèles |

Filtres de `/api/learners` : `search`, `profile`, `min_score`, `max_score`,
`min_completion`, `max_completion`, `max_login_frequency`, `sort_by`, `sort_dir`,
`page`, `page_size`.

### Administrateur

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/admin/overview` | admin | Vue d'ensemble du système |
| GET | `/api/admin/users` | admin | Liste des comptes |
| PATCH | `/api/admin/users/{id}` | admin | Modifier rôle / état |
| POST | `/api/admin/users/{id}/delete` | admin | Supprimer (confirmation par e-mail obligatoire) |
| GET | `/api/admin/activity` | admin | Activité récente réelle |
| GET | `/api/admin/recommendations` | admin | Dernières recommandations |
| GET | `/api/admin/learners/unlinked` | admin | Apprenants importés sans compte |

### Gestion des erreurs

| Code | Situation |
|---|---|
| 401 | Absence de jeton, jeton invalide ou expiré, identifiants incorrects |
| 403 | Rôle insuffisant, ou compte désactivé |
| 404 | Ressource introuvable |
| 409 | Adresse e-mail déjà utilisée |
| 422 | Données invalides (message en français, champ par champ) |
| 503 | Base Neon injoignable ou `DATABASE_URL` absente |
| 500 | Erreur interne — message générique, **aucune trace Python n'est renvoyée au client** |

L'interface traduit chaque code en message compréhensible (`frontend/src/services/api.js`).

---

## 15. Tests

```bash
cd backend
python -m pytest -v
```

72 tests répartis en six fichiers :

| Fichier | Contenu |
|---|---|
| `tests/test_api.py` | Racine, santé, analyse de profil, recommandations, chatbot, validation, schéma OpenAPI |
| `tests/test_auth.py` | Hachage bcrypt, jetons JWT, inscription, connexion, contrôle des rôles |
| `tests/test_database.py` | Normalisation des URL Neon, schéma, index, absence d'identifiants en dur |
| `tests/test_tutor.py` | Profil ML, recommandations, conversation, statistiques, impossibilité de s'auto-noter |
| `tests/test_quiz.py` | Création et validation des quiz, non-divulgation des bonnes réponses, correction serveur, note client ignorée, attribution, résultats, évaluation hors ligne, bibliothèque et recherche TF-IDF |
| `tests/test_lesson_service.py` | Confirmation idempotente d'une leçon, isolation entre apprenants et sélection d'un quiz existant pertinent |

Les tests nécessitant la base sont **automatiquement ignorés** (avec un message explicite) si
`DATABASE_URL` est absente ou injoignable : `pytest` reste utilisable hors ligne.
Les comptes de test sont créés puis supprimés automatiquement.

Le frontend est validé par un build Vite de production, puis par un contrôle navigateur des écrans
apprenant principaux en format bureau et mobile : connexion, lecture d'une leçon, confirmation,
quiz proposé, correction et transfert d'une question vers l'AI Tutor.

---

## 16. Structure du projet

```text
teachium_ai_tutor_project/
│
├── backend/
│   ├── app/
│   │   ├── main.py                     API FastAPI, CORS, gestion d'erreurs, /health
│   │   ├── core/
│   │   │   ├── config.py               Lecture du .env, normalisation de l'URL Neon
│   │   │   └── security.py             bcrypt + JWT
│   │   ├── db/
│   │   │   ├── database.py             Moteur SQLAlchemy adapté à Neon
│   │   │   └── models.py               12 tables ORM, relations, index, contraintes
│   │   ├── schemas/
│   │   │   ├── learner.py              Schémas d'origine (étendus)
│   │   │   ├── auth.py                 Inscription, connexion, jetons
│   │   │   ├── tutor.py                Apprenants, recommandations, chat, statistiques
│   │   │   └── quiz.py                 Quiz, copies, résultats, fiches de cours
│   │   ├── api/
│   │   │   ├── deps.py                 Session BD, utilisateur courant, contrôle de rôle
│   │   │   └── routes/
│   │   │       ├── auth.py             Authentification
│   │   │       ├── learners.py         Apprenants, activité, analyse
│   │   │       ├── tutor.py            AI Tutor et recommandations
│   │   │       ├── quizzes.py          Quiz : passage, création, attribution, résultats
│   │   │       ├── courses.py          Bibliothèque de cours
│   │   │       ├── ml.py               Endpoints ML sans état (conservés)
│   │   │       ├── dashboard.py        Statistiques et évaluation des modèles
│   │   │       └── admin.py            Administration
│   │   ├── services/
│   │   │   ├── lesson_service.py       Progression des leçons et choix d'un quiz existant
│   │   │   ├── profile_service.py      EXISTANT — K-Means + arbre (+ confiance)
│   │   │   ├── recommendation_service.py  EXISTANT — inchangé
│   │   │   ├── chatbot_service.py      EXISTANT — inchangé
│   │   │   ├── data_service.py         EXISTANT — lecture CSV
│   │   │   ├── tutor_service.py        NOUVEAU — intentions + contexte + moteurs
│   │   │   ├── quiz_service.py         NOUVEAU — correction serveur des copies
│   │   │   ├── knowledge_service.py    NOUVEAU — recherche TF-IDF dans les cours
│   │   │   └── stats_service.py        NOUVEAU — statistiques SQL
│   │   ├── models/                     Artefacts .joblib entraînés
│   │   └── data/                       Dataset CSV et métriques JSON
│   ├── scripts/
│   │   ├── init_database.py            NOUVEAU — initialisation complète
│   │   ├── import_dataset.py           NOUVEAU — import CSV vers Neon
│   │   ├── seed_users.py               NOUVEAU — comptes de démonstration
│   │   ├── generate_dataset.py         EXISTANT
│   │   ├── train_models.py             EXISTANT
│   │   └── generate_diagrams.py        EXISTANT
│   ├── tests/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── .env                            (non commité)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Layout.jsx              Sidebar + en-tête + navigation par rôle
│   │   │   ├── TutorFeedback.jsx       Bilan des erreurs + questions vers l'AI Tutor
│   │   │   └── ui.jsx                  Card, StatCard, badges, alertes, confirmation
│   │   ├── pages/
│   │   │   ├── Login.jsx               Connexion + comptes de démonstration
│   │   │   ├── Register.jsx            Inscription
│   │   │   ├── LearnerDashboard.jsx    Tableau de bord apprenant
│   │   │   ├── AITutor.jsx             Chat avec le tuteur
│   │   │   ├── Recommendations.jsx     Recommandations et historique
│   │   │   ├── MyQuizzes.jsx           Quiz attribués et historique des copies
│   │   │   ├── TakeQuiz.jsx            Passage d'un quiz + correction
│   │   │   ├── AttemptReview.jsx       Relecture d'une copie corrigée
│   │   │   ├── QuizManager.jsx         Création, attribution, résultats (formateur)
│   │   │   ├── Courses.jsx             Bibliothèque de cours (lecture + gestion)
│   │   │   ├── TrainerDashboard.jsx    Statistiques de la promotion
│   │   │   ├── LearnerList.jsx         Liste filtrable des apprenants
│   │   │   ├── LearnerDetail.jsx       Fiche détaillée
│   │   │   ├── ModelEvaluation.jsx     Métriques expliquées
│   │   │   ├── AdminDashboard.jsx      Vue d'ensemble système
│   │   │   ├── AdminUsers.jsx          Gestion des comptes
│   │   │   ├── AdminActivity.jsx       Activité système
│   │   │   └── Simulator.jsx           Banc d'essai des modèles
│   │   ├── services/api.js             Axios, JWT, messages d'erreur
│   │   ├── context/AuthContext.jsx     Session et rôles
│   │   ├── App.jsx                     Routes protégées
│   │   ├── main.jsx
│   │   └── styles.css                  Design system
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
│
├── dashboard/dashboard.py              Streamlit historique (optionnel)
├── figures/                            Graphiques du rapport
├── diagrams/                           Sources PlantUML
├── reports/                            Rapport de stage LaTeX
├── docs/
├── setup_backend.bat / .sh
├── run_backend.bat / .sh
├── run_frontend.bat / .sh
├── run_dashboard_streamlit.bat
├── .gitignore
└── README.md
```

---

## 17. Glossaire technique

**K-Means** — Algorithme de classification **non supervisée**. Il partitionne les apprenants en
*k* groupes en plaçant *k* centres et en attribuant chaque apprenant au centre le plus proche,
puis en déplaçant les centres jusqu'à stabilisation. Ici *k* = 5. Il n'utilise **aucune
étiquette** : il découvre les groupes dans les données.

**Arbre de décision** — Algorithme **supervisé** apprenant une cascade de tests sur les
variables. Chaque nœud pose une question, chaque feuille donne un profil. Sa force est
l'explicabilité : on peut montrer à un formateur exactement pourquoi un apprenant a été classé
« En difficulté ».

**StandardScaler** — Met toutes les variables à la même échelle (moyenne 0, écart-type 1).
Indispensable avant K-Means, qui raisonne en distances.

**Moteur de recommandation** — Ici un système à base de règles : à chaque profil correspond un
ensemble de ressources, ajusté selon les indicateurs de l'apprenant. Transparent et auditable,
ce qui convient à un contexte pédagogique.

**NLP (traitement automatique du langage)** — Domaine de l'IA traitant le texte. Le tuteur en
utilise la forme la plus simple : la **détection de mots-clés** dans la question posée.
Il n'y a ni compréhension sémantique profonde, ni génération de texte apprise.

**LLM (grand modèle de langage)** — Modèle génératif entraîné sur d'immenses corpus (type GPT).
**Le projet n'en utilise pas.** L'architecture prévoit son intégration future (voir §13).

**FastAPI** — Framework web Python asynchrone. Il valide automatiquement les données via
Pydantic et génère la documentation Swagger.

**Pydantic** — Bibliothèque de validation : elle garantit qu'un score reste entre 0 et 100
avant même d'atteindre les modèles.

**JWT (JSON Web Token)** — Jeton signé renvoyé à la connexion et présenté à chaque requête.
Il contient l'identifiant et le rôle, et une signature qui empêche toute falsification.

**bcrypt** — Fonction de hachage lente et salée pour les mots de passe. Aucun mot de passe
n'est stocké en clair, et deux comptes ayant le même mot de passe ont des empreintes différentes.

**React** — Bibliothèque JavaScript d'interfaces à base de composants.

**Vite** — Outil de développement et de build de l'application React.

**Neon PostgreSQL** — PostgreSQL managé et *serverless* dans le cloud. Aucune installation
locale ; l'instance se met en veille automatiquement et redémarre à la première requête.

**SQLAlchemy** — ORM Python : les tables sont décrites par des classes et les requêtes écrites
en Python plutôt qu'en SQL brut.

---

## 18. Limites connues

1. **Le tuteur n'est pas un LLM.** Il combine reconnaissance d'intention par mots-clés et
   recherche TF-IDF dans la bibliothèque de cours. Il ne comprend pas le sens des phrases et ne
   génère pas de texte nouveau : il sélectionne des réponses et cite ses sources. Une question
   dont le vocabulaire s'écarte trop des fiches ne trouvera pas de correspondance — le tuteur le
   dit alors explicitement plutôt que d'inventer. Ce choix est assumé, affiché dans l'interface,
   et l'architecture permet de brancher un LLM sans refonte.

2. **La bibliothèque de cours conditionne les réponses de contenu.** 15 fiches couvrent les cinq
   filières du dataset. Toute notion absente de la bibliothèque est hors de portée du tuteur ; il
   suffit d'ajouter une fiche depuis l'espace formateur pour l'y intégrer, l'index de recherche
   étant reconstruit automatiquement.

3. **Les questions d'un quiz ne sont plus modifiables après le premier passage** (réponse `409`).
   C'est délibéré : modifier une question fausserait les copies déjà corrigées. Pour une version
   révisée, il faut créer un nouveau quiz.

4. **Les quiz sont à choix unique.** Réponses multiples, questions ouvertes, images et
   chronomètre bloquant ne sont pas gérés.

5. **Le dataset est simulé.** Les 350 apprenants sont générés par `scripts/generate_dataset.py`.
   Les métriques du modèle (84 % d'exactitude) sont donc mesurées sur des données synthétiques
   et ne préjugent pas de performances sur données réelles. Pour passer à des données
   authentiques, il suffit de remplacer le CSV en conservant les mêmes colonnes, puis de relancer
   `train_models.py` et `import_dataset.py`.

6. **Le profil de référence sert de cible d'entraînement.** L'arbre apprend la colonne
   `true_profile` du dataset simulé. Le clustering K-Means est utilisé comme information
   complémentaire et non comme cible.

7. **La matrice de confusion complète n'est pas stockée en JSON.** `model_metrics.json` ne
   contient que le rapport de classification. L'interface en reconstruit la diagonale
   (support × rappel) ; la matrice complète reste consultable dans
   `figures/confusion_matrix.png`. La stocker intégralement demanderait de modifier
   `train_models.py` et de réentraîner.

8. **Pas de migrations versionnées.** Le schéma est créé par `create_all()`, ce qui est adapté à
   un prototype. Un passage en production justifierait Alembic pour gérer les évolutions de
   schéma.

9. **Réinitialisation de mot de passe par e-mail absente.** Un administrateur peut désactiver
   un compte ; l'utilisateur peut changer son mot de passe une fois connecté. Il n'y a pas de
   procédure « mot de passe oublié », faute de service d'envoi d'e-mails.

10. **Instance Neon gratuite en veille.** La toute première requête après une période
   d'inactivité peut prendre quelques secondes. Pensez à ouvrir
   <http://127.0.0.1:8000/health> avant une démonstration pour réveiller la base.

11. **Le tableau de bord Streamlit est conservé à titre de référence.** Il n'est pas nécessaire
   au fonctionnement de l'application : l'interface principale est le frontend React.

---

## Licence et contexte

Projet réalisé dans le cadre d'un stage : *Développement d'un système de tutorat intelligent
basé sur l'IA pour la personnalisation des parcours d'apprentissage* — **TEACHIUM**.
Le rapport complet se trouve dans `reports/rapport_stage_teachium.tex`.
