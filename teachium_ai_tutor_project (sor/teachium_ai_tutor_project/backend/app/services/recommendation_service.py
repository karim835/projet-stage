def recommend_content(profile: str, average_score: float, completion_rate: float, failed_quizzes: int, satisfaction_score: float = 3.0) -> dict:
    profile = profile.strip()

    if profile == "En difficulté":
        content = [
            "Cours de révision des notions de base",
            "Vidéo explicative courte",
            "Quiz de renforcement progressif",
            "Exercices corrigés avec feedback",
        ]
        reason = "Le score est faible et plusieurs quiz sont échoués. L'apprenant a besoin de consolider les bases."
        priority = "Haute"
    elif profile == "Débutant":
        content = [
            "Module d'introduction",
            "Exercices guidés",
            "Quiz facile de validation",
        ]
        reason = "Le niveau est encore initial. Un parcours guidé facilite l'acquisition progressive des compétences."
        priority = "Moyenne"
    elif profile == "Moyen":
        content = [
            "Exercices standards",
            "Quiz de progression",
            "Résumé de cours",
        ]
        reason = "Les résultats sont acceptables, mais l'apprenant peut améliorer sa maîtrise par de la pratique régulière."
        priority = "Normale"
    elif profile == "Avancé":
        content = [
            "Contenu avancé",
            "Mini-projet pratique",
            "Quiz de niveau supérieur",
        ]
        reason = "L'apprenant maîtrise les notions principales et peut passer à des contenus plus complexes."
        priority = "Normale"
    elif profile == "Peu actif":
        content = [
            "Parcours court de reprise",
            "Rappel motivationnel",
            "Objectif hebdomadaire simple",
        ]
        reason = "L'activité ou la complétion est faible. Un parcours court peut aider à reprendre progressivement."
        priority = "Haute"
    else:
        content = ["Diagnostic pédagogique complémentaire", "Quiz de positionnement"]
        reason = "Le profil n'est pas reconnu. Un diagnostic complémentaire est recommandé."
        priority = "Moyenne"

    # Ajustements complémentaires selon les indicateurs.
    if completion_rate < 40 and "Parcours court de reprise" not in content:
        content.append("Parcours court de reprise")
    if failed_quizzes >= 3 and "Quiz de renforcement progressif" not in content:
        content.append("Quiz de renforcement progressif")
    if satisfaction_score < 2.5:
        content.append("Message d'accompagnement personnalisé")

    return {
        "recommended_content": content,
        "reason": reason,
        "priority": priority,
    }
