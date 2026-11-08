# Répartition des tâches jour par jour - Stage TEACHIUM

## Semaine 1 - Cadrage et données

### Jour 1 - Compréhension du besoin
- Étudier TEACHIUM, son domaine e-learning et la mission.
- Poser les questions sur la plateforme, les données et les attentes IA.
- Définir le MVP réalisable en un mois.

**Résultat :** notes de cadrage et MVP validé.

### Jour 2 - Cahier des charges
- Rédiger contexte, problématique, objectifs, acteurs, besoins fonctionnels et non fonctionnels.
- Définir livrables, contraintes et critères de réussite.

**Résultat :** cahier des charges initial.

### Jour 3 - Analyse des données disponibles
- Lister les données nécessaires : scores, quiz, temps passé, complétion, satisfaction.
- Confirmer si les données sont réelles ou simulées.

**Résultat :** tableau des données disponibles et manquantes.

### Jour 4 - Dataset
- Nettoyer les données ou créer un dataset simulé.
- Générer `app/data/learners_dataset.csv`.

**Résultat :** dataset exploitable.

### Jour 5 - Analyse exploratoire
- Produire statistiques et graphiques.
- Observer les distributions et relations entre variables.

**Résultat :** figures dans `figures/`.

## Semaine 2 - Intelligence artificielle

### Jour 6 - Clustering
- Normaliser les variables.
- Appliquer K-Means.
- Utiliser la méthode Elbow.

**Résultat :** clusters apprenants et `elbow_method.png`.

### Jour 7 - Interprétation des clusters
- Nommer les groupes pédagogiques.
- Décrire chaque profil.

**Résultat :** dataset avec clusters et profils.

### Jour 8 - Arbre de décision
- Entraîner un `DecisionTreeClassifier`.
- Évaluer accuracy, precision, recall et F1-score.

**Résultat :** modèle sauvegardé et matrice de confusion.

### Jour 9 - Moteur de recommandation
- Créer les règles pédagogiques par profil.
- Tester les recommandations.

**Résultat :** `recommendation_service.py`.

### Jour 10 - Assistant conversationnel
- Créer un chatbot simple par mots-clés.
- Répondre aux questions sur profil, recommandation et progression.

**Résultat :** `chatbot_service.py`.

## Semaine 3 - Intégration

### Jour 11 - Backend API REST
- Créer l'application FastAPI.
- Ajouter la route racine.

**Résultat :** API fonctionnelle.

### Jour 12 - Endpoint analyse de profil
- Créer `POST /api/profile/analyze`.

**Résultat :** profil retourné en JSON.

### Jour 13 - Endpoint recommandations
- Créer `POST /api/recommendations`.

**Résultat :** recommandations retournées en JSON.

### Jour 14 - Endpoint chatbot
- Créer `POST /api/chatbot/ask`.

**Résultat :** réponse conversationnelle retournée.

### Jour 15 - Dashboard
- Construire l'interface Streamlit.
- Afficher KPI, graphiques et formulaire de test.

**Résultat :** dashboard fonctionnel.

## Semaine 4 - Tests et finalisation

### Jour 16 - Évaluation
- Lire les métriques du modèle.
- Interpréter les résultats.

**Résultat :** tableau d'évaluation.

### Jour 17 - Tests fonctionnels
- Tester le flux complet : profil, recommandation, chatbot, dashboard.

**Résultat :** tests validés.

### Jour 18 - Nettoyage du projet
- Organiser les fichiers.
- Ajouter README, scripts et documentation.

**Résultat :** projet prêt pour VS Code.

### Jour 19 - Rapport final
- Rédiger le rapport LaTeX.
- Ajouter figures, tableaux, diagrammes et références.

**Résultat :** `rapport_stage_teachium.tex` et PDF compilé.

### Jour 20 - Présentation
- Préparer la démonstration.
- Lancer API et dashboard.
- Expliquer les résultats et limites.

**Résultat :** prototype prêt à présenter.
