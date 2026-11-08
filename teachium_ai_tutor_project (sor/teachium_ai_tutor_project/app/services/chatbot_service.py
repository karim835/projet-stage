from app.services.recommendation_service import recommend_content


def chatbot_response(question: str, profile: str, recommended_content: str | None = None) -> str:
    q = question.lower().strip()
    profile = profile.strip()

    if any(word in q for word in ["profil", "niveau", "catégorie", "categorie"]):
        return (
            f"Votre profil actuel est : {profile}. Ce profil est estimé à partir de vos scores, "
            "de votre taux de complétion, de votre activité et de vos résultats aux quiz."
        )

    if any(word in q for word in ["pourquoi", "recommand", "ressource"]):
        if recommended_content:
            return (
                f"La ressource '{recommended_content}' est recommandée parce qu'elle correspond au profil {profile}. "
                "L'objectif est de proposer un contenu adapté à vos besoins pédagogiques actuels."
            )
        return (
            f"La recommandation est liée à votre profil {profile}. Elle vise à vous orienter vers le contenu le plus utile "
            "pour progresser de manière personnalisée."
        )

    if any(word in q for word in ["progresser", "conseil", "améliorer", "ameliorer"]):
        if profile == "En difficulté":
            return "Conseil : commencez par revoir les notions de base, puis refaites un quiz court après chaque leçon."
        if profile == "Peu actif":
            return "Conseil : fixez un objectif simple, par exemple terminer une courte leçon par jour pendant une semaine."
        if profile == "Avancé":
            return "Conseil : passez à des exercices avancés ou à un mini-projet pour consolider vos compétences."
        return "Conseil : gardez un rythme régulier et entraînez-vous avec des quiz de progression."

    if any(word in q for word in ["cours", "revoir", "réviser", "reviser"]):
        if profile == "En difficulté":
            return "Vous devriez revoir les cours fondamentaux et refaire les quiz liés aux notions non maîtrisées."
        if profile == "Avancé":
            return "Vous pouvez revoir rapidement les résumés puis passer aux ressources avancées."
        return "Vous pouvez revoir le dernier cours non terminé puis passer un quiz de validation."

    if any(word in q for word in ["quiz", "test", "exercice"]):
        return "Je vous conseille de faire un quiz court après chaque ressource pour vérifier votre compréhension."

    return (
        "Je peux vous aider à comprendre votre profil, expliquer vos recommandations, choisir un cours à revoir "
        "ou vous donner des conseils de progression."
    )
