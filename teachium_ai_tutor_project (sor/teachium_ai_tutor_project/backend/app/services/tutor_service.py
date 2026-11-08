"""Orchestration de l'AI Tutor.

Ce module fait le lien entre :

* les **services ML existants** (`profile_service`, `recommendation_service`,
  `chatbot_service`) — source unique de vérité pédagogique ;
* la **base de données** (profil, recommandations, quiz, historique) ;
* la **bibliothèque de cours** (`knowledge_service`) pour les questions portant
  sur le contenu des cours ;
* l'**API REST** consommée par le frontend React.

Architecture du moteur conversationnel
--------------------------------------
Le tuteur repose sur l'interface `TutorEngine`. Une seule implémentation est
active : `RuleBasedTutorEngine`. Elle combine trois mécanismes :

1. **Reconnaissance d'intention** — une vingtaine d'intentions pédagogiques,
   chacune décrite par des expressions déclenchantes pondérées ;
2. **Ancrage dans les données réelles** — chaque réponse cite les indicateurs,
   résultats de quiz et recommandations lus en base pour cet apprenant ;
3. **Recherche documentaire TF-IDF** — pour toute question portant sur le
   contenu d'un cours, la bibliothèque est interrogée et la fiche source citée.

Ce n'est **pas** un grand modèle de langage, et l'application ne le prétend
jamais : l'API expose `engine: "rules"` et l'interface l'affiche.

Pour brancher un vrai LLM plus tard, il suffit d'écrire une classe respectant
`TutorEngine` et de l'enregistrer via `register_engine()`.
"""

from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Learner, LearnerProfile, Recommendation
from app.services.knowledge_service import normalize
from app.services.profile_service import analyze_profile
from app.services.recommendation_service import recommend_content

MAX_QUESTION_LENGTH = 1000

#: Seuil de similarité TF-IDF en dessous duquel on considère que la
#: bibliothèque ne contient pas la réponse.
KB_MIN_SCORE = 0.06


class EmptyQuestionError(ValueError):
    """La question envoyée au tuteur est vide."""


@dataclass
class TutorContext:
    """Tout ce que le tuteur sait de l'apprenant au moment de répondre."""

    profile: str
    metrics: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    reason: str | None = None
    risk_level: str | None = None
    cluster: int | None = None
    confidence: float | None = None
    explanation: str | None = None
    category: str | None = None
    student_id: str | None = None
    name: str | None = None
    quiz_summary: dict = field(default_factory=dict)
    pending_quizzes: list[dict] = field(default_factory=list)
    promotion: dict = field(default_factory=dict)
    #: Session de base de données, nécessaire à la recherche documentaire.
    db: Session | None = None


class TutorEngine(ABC):
    """Contrat commun à tous les moteurs de réponse de l'AI Tutor."""

    name: str = "abstract"
    label: str = ""

    @abstractmethod
    def answer(self, question: str, context: TutorContext) -> str:
        """Produit une réponse textuelle à partir de la question et du contexte."""


# ---------------------------------------------------------------------------
#  Utilitaires de formatage
# ---------------------------------------------------------------------------


def prepare_text(text: str) -> str:
    """Prépare un texte pour la comparaison d'expressions.

    Minuscules, suppression des accents, puis remplacement des apostrophes,
    traits d'union et ponctuations par des espaces. « Qu'est-ce que » et
    « qu est ce que » deviennent ainsi la même chaîne.
    """
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalize(text))
    return f" {cleaned.strip()} "


def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "n/d"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _bullets(items) -> str:
    return "\n".join(f"• {item}" for item in items)


def _compare(value, reference, unit: str = "") -> str:
    """Phrase de comparaison avec la moyenne de la promotion."""
    if value is None or reference is None:
        return ""
    diff = float(value) - float(reference)
    if abs(diff) < 1:
        return f"C'est au niveau de la moyenne de la promotion ({_fmt(reference)}{unit})."
    if diff > 0:
        return f"C'est {_fmt(abs(diff))}{unit} au-dessus de la moyenne de la promotion ({_fmt(reference)}{unit})."
    return f"C'est {_fmt(abs(diff))}{unit} en dessous de la moyenne de la promotion ({_fmt(reference)}{unit})."


# ---------------------------------------------------------------------------
#  Moteur à base de règles
# ---------------------------------------------------------------------------


class RuleBasedTutorEngine(TutorEngine):
    """Reconnaissance d'intention + données réelles + recherche documentaire."""

    name = "rules"
    label = "Moteur à base de règles (intentions + recherche documentaire) — pas un LLM"

    #: Intentions de conseil : une fiche de cours nettement pertinente leur est
    #: préférée. « Comment réussir ma soutenance ? » doit renvoyer la fiche sur
    #: la présentation orale, pas un conseil générique sur la progression.
    ADVISORY_INTENTS = {"progress", "course_review", "study_plan"}

    #: Score TF-IDF au-delà duquel une fiche est considérée comme nettement
    #: pertinente et prime sur une intention de conseil.
    STRONG_KB_SCORE = 0.13

    def answer(self, question: str, context: TutorContext) -> str:
        text = normalize(question)
        intent, score = self._detect_intent(text)

        # 1. Question portant explicitement sur du contenu, ou intention trop
        #    faible pour être fiable : la bibliothèque est interrogée d'abord.
        if intent in {"course_content", None} or score < 2:
            documented = self._answer_from_library(question, context)
            if documented:
                return documented

        # 2. Intention de conseil : la bibliothèque prime si elle a une réponse
        #    nettement pertinente sur le sujet exact de la question.
        elif intent in self.ADVISORY_INTENTS:
            documented = self._answer_from_library(
                question, context, min_score=self.STRONG_KB_SCORE
            )
            if documented:
                return documented

        handler = getattr(self, f"_intent_{intent}", None) if intent else None
        if handler is not None:
            answer = handler(question, context)
            if answer:
                return answer

        # 3. Dernier recours : recherche documentaire puis message d'orientation.
        documented = self._answer_from_library(question, context)
        return documented or self._fallback(context)

    # --- Détection d'intention ---------------------------------------------

    #: Chaque intention est décrite par des expressions et leur poids.
    #: Une expression de plusieurs mots vaut plus qu'un mot isolé : elle est
    #: bien plus discriminante.
    INTENTS: dict[str, list[tuple[str, int]]] = {
        "greeting": [("bonjour", 5), ("bonsoir", 5), ("salut", 5), ("hello", 5), ("coucou", 5)],
        "thanks": [("merci", 5), ("super", 2), ("parfait", 2), ("d'accord", 2)],
        "help": [
            ("que peux tu faire", 8), ("que sais tu faire", 8), ("aide moi", 6), ("aide", 3),
            ("comment ca marche", 6), ("tes fonctions", 5), ("tu sers a quoi", 7),
        ],
        "profile": [
            ("mon profil", 8), ("quel est mon profil", 10), ("mon niveau", 7),
            ("ma categorie", 6), ("profil", 3), ("niveau", 2), ("classe", 2),
        ],
        "profile_why": [
            ("pourquoi ce profil", 10), ("comment est calcule mon profil", 10),
            ("comment tu determines", 8), ("sur quoi tu te bases", 8),
            ("pourquoi je suis classe", 9), ("comment mon profil est determine", 10),
        ],
        "score": [
            ("mon score", 8), ("ma note", 7), ("ma moyenne", 8), ("mes notes", 7),
            ("score moyen", 7), ("combien j'ai", 6), ("score", 2), ("moyenne", 3), ("note", 2),
        ],
        "completion": [
            ("taux de completion", 9), ("ma completion", 8), ("mon avancement", 8),
            ("ou j'en suis", 7), ("completion", 4), ("avancement", 4), ("pourcentage", 3),
        ],
        "time": [
            ("temps passe", 8), ("combien de temps", 8), ("mes heures", 6),
            ("temps d'apprentissage", 8), ("duree", 3), ("heures", 3), ("temps", 2),
        ],
        "quiz_results": [
            ("mes resultats", 8), ("mes quiz", 7), ("resultats des quiz", 9),
            ("mes notes de quiz", 9), ("comment j'ai fait", 6), ("mes scores", 7),
            ("quiz deja passe", 9), ("historique des quiz", 9), ("quiz", 2),
        ],
        "quiz_pending": [
            ("quiz a faire", 10), ("quiz a passer", 10), ("prochain quiz", 9),
            ("quiz assigne", 9), ("mes devoirs", 8), ("qu'est ce que je dois faire", 8),
            ("quiz en attente", 9), ("travail a rendre", 8), ("quiz dois je", 10),
            ("dois je passer", 8), ("quiz restant", 9), ("quiz me reste", 9),
            ("quiz suivant", 8), ("quiz", 2),
        ],
        "weaknesses": [
            ("mes points faibles", 10), ("mes difficultes", 9), ("mes erreurs", 9),
            ("ou je bloque", 9), ("ce que je rate", 8), ("mes lacunes", 9),
            ("ce que je ne comprends pas", 8), ("point faible", 7), ("faiblesse", 6),
        ],
        "recommendations": [
            ("pourquoi cette recommandation", 10), ("pourquoi ai je recu", 9),
            ("mes recommandations", 9), ("quelles ressources", 8),
            ("recommand", 5), ("ressource", 3),
        ],
        "progress": [
            ("comment progresser", 10), ("comment m'ameliorer", 10), ("comment faire mieux",  9),
            ("un conseil", 7), ("des conseils", 7), ("progresser", 5), ("ameliorer", 5),
            ("comment reussir", 7), ("conseil", 3),
        ],
        "course_review": [
            ("quel cours revoir", 10), ("que dois je reviser", 10), ("quoi reviser", 9),
            ("cours a revoir", 9), ("reviser", 5), ("revision", 5), ("revoir", 4),
        ],
        "study_plan": [
            ("comment m'organiser", 10), ("planning", 7), ("plan de travail", 9),
            ("combien de temps par jour", 10), ("methode de travail", 9),
            ("organiser mon temps", 9), ("rythme", 5), ("organiser", 4),
        ],
        "motivation": [
            ("je suis decourage", 10), ("j'abandonne", 10), ("c'est trop dur", 9),
            ("je n'y arrive pas", 10), ("demotive", 9), ("je suis perdu", 8),
            ("stresse", 6), ("difficile", 4), ("fatigue", 4),
        ],
        "comparison": [
            ("par rapport aux autres", 10), ("moyenne de la classe", 9),
            ("moyenne de la promotion", 10), ("les autres apprenants", 8),
            ("mon classement", 8), ("je me situe", 8), ("comparaison", 6), ("promotion", 4),
        ],
        "system_explanation": [
            ("k means", 10), ("kmeans", 10), ("arbre de decision", 10), ("clustering", 9),
            ("machine learning", 9), ("intelligence artificielle", 8), ("algorithme", 7),
            ("comment fonctionne le systeme", 10), ("cluster", 6), ("modele", 4),
        ],
        "library": [
            ("quels cours", 9), ("liste des cours", 10), ("bibliotheque", 9),
            ("quels sujets", 8), ("sur quoi tu peux m'aider", 9), ("catalogue", 7),
        ],
        "next_step": [
            ("par ou commencer", 10), ("prochaine etape", 10), ("que faire maintenant", 10),
            ("quoi faire", 7), ("par quoi commencer", 10),
        ],
        "satisfaction": [("satisfaction", 7), ("content de la formation", 8)],
        "course_content": [
            ("explique moi", 8), ("c'est quoi", 7), ("qu'est ce que", 6), ("definition", 7),
            ("comment faire", 5), ("a quoi sert", 7), ("difference entre", 8),
            ("exemple de", 6), ("comment utiliser", 7),
        ],
    }

    #: Index des expressions déclenchantes, normalisées une seule fois.
    _normalized_intents: dict[str, list[tuple[str, int]]] | None = None

    @classmethod
    def _patterns(cls) -> dict[str, list[tuple[str, int]]]:
        if cls._normalized_intents is None:
            cls._normalized_intents = {
                intent: [(prepare_text(phrase), weight) for phrase, weight in patterns]
                for intent, patterns in cls.INTENTS.items()
            }
        return cls._normalized_intents

    def _detect_intent(self, text: str) -> tuple[str | None, int]:
        """Score chaque intention et retient la mieux notée.

        Le texte et les expressions sont préparés de la même façon (accents,
        apostrophes et traits d'union neutralisés), pour que « quiz dois-je
        passer » et « quiz dois je passer » soient reconnus à l'identique.
        """
        prepared = prepare_text(text)
        best: str | None = None
        best_score = 0
        for intent, patterns in self._patterns().items():
            score = sum(weight for phrase, weight in patterns if phrase in prepared)
            if score > best_score:
                best, best_score = intent, score
        return best, best_score

    # --- Recherche documentaire --------------------------------------------

    def _answer_from_library(
        self, question: str, context: TutorContext, min_score: float = KB_MIN_SCORE
    ) -> str | None:
        """Cherche la réponse dans la bibliothèque de cours."""
        if context.db is None:
            return None

        from app.services import knowledge_service

        hits = knowledge_service.search(context.db, question, top_k=3, category=context.category)
        if not hits or hits[0]["score"] < min_score:
            return None

        top = hits[0]
        resource = top["resource"]
        passage = knowledge_service.best_passage(resource, question)

        parts = [
            f"D'après la fiche « {resource.title} » ({resource.category}, niveau {resource.level}) :",
            "",
            passage,
        ]

        others = [h for h in hits[1:] if h["score"] >= KB_MIN_SCORE]
        if others:
            titles = ", ".join(f"« {h['resource'].title} »" for h in others)
            parts += ["", f"Fiches également pertinentes : {titles}."]

        parts += [
            "",
            "Vous pouvez consulter la fiche complète dans la bibliothèque de cours "
            "(menu « Cours »).",
        ]
        return "\n".join(parts)

    # --- Intentions ---------------------------------------------------------

    def _intent_greeting(self, question: str, c: TutorContext) -> str:
        name = (c.name or "").split("—")[0].strip() or "à vous"
        return (
            f"Bonjour {name} ! Je suis l'AI Tutor de TEACHIUM.\n\n"
            f"Votre profil actuel est : {c.profile}. "
            f"Score moyen {_fmt(c.metrics.get('average_score'))}/100, "
            f"complétion {_fmt(c.metrics.get('completion_rate'))} %.\n\n"
            "Posez-moi une question sur votre profil, vos résultats, vos recommandations, "
            "ou sur le contenu d'un cours."
        )

    def _intent_thanks(self, question: str, c: TutorContext) -> str:
        return (
            "Avec plaisir. N'hésitez pas si vous voulez comprendre une recommandation, "
            "réviser une notion ou savoir quel quiz passer ensuite."
        )

    def _intent_help(self, question: str, c: TutorContext) -> str:
        return (
            "Voici ce que je peux faire :\n\n"
            + _bullets([
                "expliquer votre profil pédagogique et comment il est calculé,",
                "détailler vos indicateurs : score, complétion, temps, quiz échoués,",
                "vous situer par rapport à la moyenne de la promotion,",
                "expliquer pourquoi telle ressource vous est recommandée,",
                "lister les quiz qui vous sont attribués et ceux qu'il reste à réussir,",
                "analyser vos erreurs de quiz pour cibler vos points faibles,",
                "répondre à une question sur le contenu d'un cours à partir de la bibliothèque,",
                "vous proposer une méthode de travail adaptée à votre profil.",
            ])
            + "\n\nJe fonctionne par reconnaissance de mots-clés et recherche documentaire, "
            "pas comme un modèle de langage génératif : soyez plutôt direct dans vos questions."
        )

    def _intent_profile(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        lines = [
            f"Votre profil actuel est : {c.profile}.",
            "",
            c.explanation or "",
            "",
            "Vos indicateurs actuels :",
            _bullets([
                f"score moyen : {_fmt(m.get('average_score'))}/100",
                f"taux de complétion : {_fmt(m.get('completion_rate'))} %",
                f"quiz échoués : {int(m.get('failed_quizzes') or 0)} sur {int(m.get('quiz_attempts') or 0)} tentative(s)",
                f"connexions par semaine : {int(m.get('login_frequency') or 0)}",
                f"temps d'apprentissage : {_fmt(m.get('time_spent_hours'))} heures",
            ]),
        ]
        if c.risk_level:
            lines += ["", f"Niveau de risque estimé : {c.risk_level}."]
        if c.confidence is not None:
            lines += [
                f"Confiance du modèle sur ce classement : {round(c.confidence * 100)} %."
            ]
        return "\n".join(line for line in lines if line != "" or True).strip()

    def _intent_profile_why(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        return (
            f"Votre profil « {c.profile} » est déterminé automatiquement par un **arbre de "
            "décision** entraîné sur les données de la promotion. Il examine sept variables :\n\n"
            + _bullets([
                f"score moyen : {_fmt(m.get('average_score'))}/100",
                f"temps passé : {_fmt(m.get('time_spent_hours'))} h",
                f"taux de complétion : {_fmt(m.get('completion_rate'))} %",
                f"quiz tentés : {int(m.get('quiz_attempts') or 0)}",
                f"quiz échoués : {int(m.get('failed_quizzes') or 0)}",
                f"connexions par semaine : {int(m.get('login_frequency') or 0)}",
                f"satisfaction : {_fmt(m.get('satisfaction_score'))}/5",
            ])
            + "\n\n"
            + (f"En parallèle, un algorithme K-Means vous a placé dans le groupe n°{c.cluster}, "
               "qui rassemble les apprenants aux comportements similaires.\n\n" if c.cluster is not None else "")
            + (f"Le modèle attribue une confiance de {round(c.confidence * 100)} % à ce classement.\n\n"
               if c.confidence is not None else "")
            + "Ce profil n'est pas figé : il est recalculé à chaque nouveau résultat de quiz."
        )

    def _intent_score(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        lines = [
            f"Votre score moyen est de {_fmt(m.get('average_score'))}/100, "
            f"calculé sur {int(m.get('quiz_attempts') or 0)} évaluation(s).",
        ]
        comparison = _compare(m.get("average_score"), c.promotion.get("average_score"))
        if comparison:
            lines.append(comparison)

        summary = c.quiz_summary or {}
        if summary.get("by_category"):
            lines += ["", "Moyenne par filière :", _bullets(
                f"{cat} : {_fmt(value)}/100" for cat, value in summary["by_category"].items()
            )]
        if summary.get("best") and summary.get("worst") and summary["attempts"] > 1:
            lines += [
                "",
                f"Meilleur résultat : « {summary['best']['quiz']} » ({_fmt(summary['best']['score'])}/100).",
                f"Résultat le plus faible : « {summary['worst']['quiz']} » ({_fmt(summary['worst']['score'])}/100).",
            ]
        if int(m.get("failed_quizzes") or 0) > 0:
            lines += ["", f"Vous avez {int(m['failed_quizzes'])} quiz en échec : ce sont eux "
                          "qui pèsent le plus sur votre moyenne."]
        return "\n".join(lines)

    def _intent_completion(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        lines = [
            f"Votre taux de complétion est de {_fmt(m.get('completion_rate'))} % "
            f"({int(m.get('completed_courses') or 0)} module(s) validé(s) sur "
            f"{int(m.get('total_courses') or 0)}).",
        ]
        comparison = _compare(m.get("completion_rate"), c.promotion.get("average_completion_rate"), " point(s)")
        if comparison:
            lines.append(comparison)
        if c.pending_quizzes:
            lines += ["", f"Il vous reste {len(c.pending_quizzes)} quiz attribué(s) à réussir :",
                      _bullets(q["title"] for q in c.pending_quizzes[:5])]
        elif float(m.get("completion_rate") or 0) < 50:
            lines += ["", "Aucun quiz n'est en attente. Demandez à votre formateur de vous en "
                          "attribuer pour faire progresser votre taux de complétion."]
        return "\n".join(lines)

    def _intent_time(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        lines = [f"Vous avez passé {_fmt(m.get('time_spent_hours'))} heures sur la plateforme."]
        comparison = _compare(m.get("time_spent_hours"), c.promotion.get("average_time_spent"), " h")
        if comparison:
            lines.append(comparison)
        logins = int(m.get("login_frequency") or 0)
        lines += ["", f"Vous vous connectez en moyenne {logins} fois par semaine."]
        if logins <= 1:
            lines.append("C'est peu : une régularité, même courte, compte davantage que de longues "
                         "sessions espacées. Visez trois connexions par semaine.")
        return "\n".join(lines)

    def _intent_quiz_results(self, question: str, c: TutorContext) -> str:
        summary = c.quiz_summary or {}
        if not summary.get("attempts"):
            return (
                "Vous n'avez encore passé aucun quiz dans l'application.\n\n"
                + (f"{len(c.pending_quizzes)} quiz vous sont attribués :\n"
                   + _bullets(q["title"] for q in c.pending_quizzes[:5])
                   if c.pending_quizzes else
                   "Aucun quiz ne vous est attribué pour l'instant. Votre formateur peut vous en "
                   "attribuer depuis son espace.")
                + "\n\nVos indicateurs actuels proviennent de votre historique de formation importé."
            )

        lines = [f"Vous avez passé {summary['attempts']} quiz. Voici vos derniers résultats :", ""]
        for item in summary["recent"]:
            mark = "réussi" if item["passed"] else "échoué"
            lines.append(f"• {item['quiz']} — {_fmt(item['score'])}/100 ({mark})")

        if summary.get("by_category"):
            lines += ["", "Moyenne par filière :", _bullets(
                f"{cat} : {_fmt(value)}/100" for cat, value in summary["by_category"].items()
            )]
        if c.pending_quizzes:
            lines += ["", f"Quiz encore à réussir : {len(c.pending_quizzes)} — "
                          + ", ".join(q["title"] for q in c.pending_quizzes[:3])]
        return "\n".join(lines)

    def _intent_quiz_pending(self, question: str, c: TutorContext) -> str:
        if not c.pending_quizzes:
            return (
                "Vous n'avez aucun quiz en attente : tous les quiz qui vous ont été attribués "
                "sont réussis. Bravo.\n\n"
                "Vous pouvez repasser un quiz pour améliorer votre note, ou consulter la "
                "bibliothèque de cours pour approfondir une notion."
            )
        lines = [f"Il vous reste {len(c.pending_quizzes)} quiz à réussir :", ""]
        for quiz in c.pending_quizzes:
            due = f" — à rendre avant le {quiz['due_date']:%d/%m/%Y}" if quiz.get("due_date") else ""
            category = f" ({quiz['category']})" if quiz.get("category") else ""
            lines.append(f"• {quiz['title']}{category}{due}")
        lines += ["", "Rendez-vous dans « Mes quiz » pour les passer. La correction est "
                      "automatique et votre profil est recalculé immédiatement."]
        return "\n".join(lines)

    def _intent_weaknesses(self, question: str, c: TutorContext) -> str:
        summary = c.quiz_summary or {}
        weak = summary.get("weak_questions") or []

        if not weak:
            m = c.metrics
            issues = []
            if float(m.get("average_score") or 0) < 50:
                issues.append("votre score moyen est faible : les bases doivent être consolidées")
            if float(m.get("completion_rate") or 0) < 40:
                issues.append("votre taux de complétion est bas : beaucoup de modules restent inachevés")
            if int(m.get("failed_quizzes") or 0) >= 3:
                issues.append(f"{int(m['failed_quizzes'])} quiz sont en échec")
            if int(m.get("login_frequency") or 0) <= 1:
                issues.append("votre fréquence de connexion est très faible")
            if not issues:
                return ("Je ne détecte pas de point faible marqué dans vos indicateurs. "
                        "Passez quelques quiz : j'analyserai alors vos erreurs question par question "
                        "pour cibler précisément les notions à revoir.")
            return ("D'après vos indicateurs, voici les points à travailler :\n\n"
                    + _bullets(issues)
                    + "\n\nPassez des quiz pour que je puisse analyser vos erreurs en détail.")

        lines = ["Voici les questions que vous avez manquées — ce sont vos notions à revoir :", ""]
        for item in weak:
            lines.append(f"• {item['question']}")
            lines.append(f"  (quiz « {item['quiz']} »"
                         + (f", filière {item['category']}" if item.get("category") else "") + ")")
            if item.get("explanation"):
                lines.append(f"  → {item['explanation']}")
        lines += ["", "Consultez les fiches correspondantes dans la bibliothèque de cours, "
                      "puis repassez le quiz."]
        return "\n".join(lines)

    def _intent_recommendations(self, question: str, c: TutorContext) -> str:
        if not c.recommendations:
            return ("Aucune recommandation n'est active pour l'instant. "
                    "Lancez une analyse depuis votre tableau de bord pour en générer.")
        lines = [
            f"Ces ressources vous sont recommandées parce que votre profil est « {c.profile} » :",
            "",
            _bullets(c.recommendations),
        ]
        if c.reason:
            lines += ["", f"Raison retenue par le moteur de recommandation : {c.reason}"]
        lines += [
            "",
            "Le moteur croise votre profil avec vos indicateurs : un taux de complétion "
            "inférieur à 40 %, au moins 3 quiz échoués ou une satisfaction basse ajoutent "
            "automatiquement des ressources de soutien.",
        ]
        return "\n".join(lines)

    def _intent_progress(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        advice: list[str] = []

        if c.profile == "En difficulté":
            advice = [
                "reprenez les notions de base avant tout nouveau contenu,",
                "faites un quiz court après chaque leçon pour vérifier votre compréhension,",
                "ne passez à la suite qu'une fois 60/100 dépassé sur la notion en cours.",
            ]
        elif c.profile == "Peu actif":
            advice = [
                "fixez-vous un objectif simple : une leçon courte par jour pendant une semaine,",
                "connectez-vous à heure fixe pour créer une habitude,",
                "commencez par le module le plus court pour relancer la dynamique.",
            ]
        elif c.profile == "Débutant":
            advice = [
                "suivez le parcours guidé dans l'ordre, sans sauter d'étape,",
                "refaites les exercices corrigés jusqu'à les réussir sans aide,",
                "notez les notions floues et revenez-y en fin de semaine.",
            ]
        elif c.profile == "Avancé":
            advice = [
                "passez à un mini-projet pratique pour ancrer vos acquis,",
                "attaquez les quiz de niveau supérieur,",
                "expliquez une notion à quelqu'un d'autre : c'est le meilleur test de maîtrise.",
            ]
        else:
            advice = [
                "gardez un rythme régulier plutôt que des sessions intensives espacées,",
                "alternez lecture de cours et quiz de progression,",
                "ciblez en priorité les notions où vous avez déjà échoué.",
            ]

        lines = [f"Conseils adaptés à votre profil « {c.profile} » :", "", _bullets(advice)]

        specifics = []
        if int(m.get("failed_quizzes") or 0) >= 3:
            specifics.append(
                f"Vous avez {int(m['failed_quizzes'])} quiz en échec. Reprendre ceux-là fera "
                "remonter votre moyenne plus vite que n'importe quel nouveau contenu."
            )
        if float(m.get("completion_rate") or 0) < 40:
            specifics.append(
                f"Votre complétion est à {_fmt(m.get('completion_rate'))} %. Terminer un module "
                "commencé vaut mieux que d'en ouvrir un nouveau."
            )
        if int(m.get("login_frequency") or 0) <= 2:
            specifics.append(
                "Votre régularité est faible. Trois connexions courtes par semaine sont plus "
                "efficaces qu'une longue session."
            )
        if c.pending_quizzes:
            specifics.append(
                f"Concrètement, commencez par : « {c.pending_quizzes[0]['title']} »."
            )
        if specifics:
            lines += ["", "Dans votre cas précis :", "", _bullets(specifics)]
        return "\n".join(lines)

    def _intent_course_review(self, question: str, c: TutorContext) -> str:
        summary = c.quiz_summary or {}
        lines: list[str] = []

        by_category = summary.get("by_category") or {}
        if by_category:
            weakest = min(by_category.items(), key=lambda kv: kv[1])
            lines += [
                f"Priorité : la filière **{weakest[0]}**, où votre moyenne est de "
                f"{_fmt(weakest[1])}/100 — c'est votre point le plus bas.",
                "",
            ]
        if summary.get("worst"):
            lines += [f"Le quiz à retravailler en premier est « {summary['worst']['quiz']} » "
                      f"({_fmt(summary['worst']['score'])}/100).", ""]

        weak = summary.get("weak_questions") or []
        if weak:
            lines += ["Notions précises que vous avez manquées :", "",
                      _bullets(item["question"] for item in weak[:3]), ""]

        if c.recommendations:
            lines += ["Ressources recommandées pour vous :", "", _bullets(c.recommendations[:4]), ""]

        if not lines:
            lines = [
                f"Votre profil est « {c.profile} ». ",
                "",
                "Passez d'abord un quiz : j'identifierai alors précisément les notions à revoir "
                "à partir de vos erreurs. En attendant, les ressources recommandées sur votre "
                "tableau de bord sont le meilleur point de départ.",
            ]
        lines.append("Les fiches correspondantes sont dans la bibliothèque de cours.")
        return "\n".join(lines)

    def _intent_study_plan(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        logins = int(m.get("login_frequency") or 0)
        hours = float(m.get("time_spent_hours") or 0)

        if c.profile in {"En difficulté", "Peu actif"}:
            plan = [
                "Lundi, mercredi, vendredi : 30 minutes de révision d'une notion de base.",
                "Après chaque session : un quiz court pour vérifier ce qui est acquis.",
                "Samedi : reprendre uniquement les questions ratées de la semaine.",
            ]
            volume = "environ 2 heures par semaine, réparties en petites sessions"
        elif c.profile == "Avancé":
            plan = [
                "Deux sessions de 1 h par semaine sur des contenus avancés.",
                "Une session de mise en pratique (mini-projet) toutes les deux semaines.",
                "Un quiz de niveau supérieur en fin de chaque module.",
            ]
            volume = "environ 3 heures par semaine"
        else:
            plan = [
                "Trois sessions de 45 minutes par semaine.",
                "Alternance : une session de cours, une session d'exercices.",
                "Un quiz de progression en fin de semaine.",
            ]
            volume = "environ 2 h 30 par semaine"

        lines = [
            f"Voici une organisation adaptée à votre profil « {c.profile} » "
            f"({volume}) :", "", _bullets(plan),
        ]
        lines += ["", f"Actuellement vous vous connectez {logins} fois par semaine pour un total "
                      f"de {_fmt(hours)} heures cumulées."]
        if logins < 3:
            lines.append("Passer à trois connexions hebdomadaires est le changement le plus "
                         "rentable que vous puissiez faire.")
        if c.pending_quizzes:
            lines += ["", f"À caler dans ce planning : {len(c.pending_quizzes)} quiz en attente, "
                          f"à commencer par « {c.pending_quizzes[0]['title']} »."]
        return "\n".join(lines)

    def _intent_motivation(self, question: str, c: TutorContext) -> str:
        m = c.metrics
        lines = [
            "C'est une réaction fréquente, et vos chiffres montrent que la situation est "
            "loin d'être bloquée.",
            "",
        ]
        positives = []
        if float(m.get("average_score") or 0) > 0:
            positives.append(f"vous avez déjà une moyenne de {_fmt(m.get('average_score'))}/100")
        if int(m.get("completed_courses") or 0) > 0:
            positives.append(f"{int(m['completed_courses'])} module(s) sont déjà validés")
        if float(m.get("time_spent_hours") or 0) > 0:
            positives.append(f"vous avez investi {_fmt(m.get('time_spent_hours'))} heures")
        if positives:
            lines += ["Ce qui est déjà acquis :", "", _bullets(positives), ""]

        lines += [
            "Une action concrète, tout de suite :",
            "",
        ]
        if c.pending_quizzes:
            lines.append(f"• passez uniquement « {c.pending_quizzes[0]['title']} », rien d'autre aujourd'hui ;")
        elif c.recommendations:
            lines.append(f"• ouvrez seulement « {c.recommendations[0]} », 20 minutes, puis arrêtez ;")
        else:
            lines.append("• choisissez une seule notion et consacrez-lui 20 minutes, puis arrêtez ;")
        lines.append("• l'objectif est de relancer la régularité, pas de tout rattraper d'un coup.")

        lines += [
            "",
            "Si la difficulté persiste, parlez-en à votre formateur : il voit vos indicateurs "
            "et peut adapter votre parcours.",
        ]
        return "\n".join(lines)

    def _intent_comparison(self, question: str, c: TutorContext) -> str:
        m, p = c.metrics, c.promotion
        if not p:
            return "Les moyennes de la promotion ne sont pas disponibles pour le moment."

        rows = [
            ("Score moyen", m.get("average_score"), p.get("average_score"), "/100"),
            ("Taux de complétion", m.get("completion_rate"), p.get("average_completion_rate"), " %"),
            ("Temps d'apprentissage", m.get("time_spent_hours"), p.get("average_time_spent"), " h"),
            ("Satisfaction", m.get("satisfaction_score"), p.get("average_satisfaction"), "/5"),
        ]
        lines = [f"Comparaison avec les {p.get('total_learners', 0)} apprenants de la promotion :", ""]
        for label, mine, avg, unit in rows:
            if mine is None or avg is None:
                continue
            diff = float(mine) - float(avg)
            marker = "au-dessus" if diff > 0.5 else ("en dessous" if diff < -0.5 else "au niveau")
            lines.append(f"• {label} : {_fmt(mine)}{unit} contre {_fmt(avg)}{unit} en moyenne — "
                         f"vous êtes {marker}.")

        lines += ["", "Attention : la moyenne de la promotion n'est pas un objectif en soi. "
                      "Votre profil pédagogique tient compte de votre situation d'ensemble, "
                      "pas d'un classement."]
        return "\n".join(lines)

    def _intent_system_explanation(self, question: str, c: TutorContext) -> str:
        text = prepare_text(question)
        blocks = []

        if any(k in text for k in ["k means", "kmeans", "cluster"]):
            blocks.append(
                "**K-Means** est un algorithme d'apprentissage non supervisé. Il répartit les "
                "apprenants en 5 groupes homogènes sans connaître leur profil à l'avance : il "
                "place 5 centres, rattache chaque apprenant au centre le plus proche, déplace "
                "les centres, et recommence jusqu'à stabilisation."
                + (f"\n\nVous appartenez au groupe n°{c.cluster}." if c.cluster is not None else "")
            )
        if any(k in text for k in ["arbre", "decision", "classification"]):
            blocks.append(
                "L'**arbre de décision** est un algorithme supervisé. Il apprend une suite de "
                "questions simples (« le score est-il inférieur à 50 ? », « y a-t-il plus de "
                "2 quiz échoués ? ») qui mènent à l'un des cinq profils. C'est lui qui détermine "
                "le profil affiché. Son intérêt est d'être explicable : on peut retracer "
                "exactement le chemin qui a mené à la décision."
                + (f"\n\nDans votre cas, il a retenu « {c.profile} »"
                   + (f" avec une confiance de {round(c.confidence * 100)} %." if c.confidence is not None else ".")
                   )
            )
        if not blocks:
            blocks.append(
                "Le système fonctionne en quatre temps :\n\n"
                + _bullets([
                    "vos données sont normalisées (mise à la même échelle),",
                    "K-Means vous place dans un groupe d'apprenants au comportement proche,",
                    "un arbre de décision détermine votre profil pédagogique,",
                    "un moteur de règles en déduit des ressources adaptées.",
                ])
                + "\n\nTout est recalculé à chaque nouveau résultat de quiz."
            )

        blocks.append(
            "Ces modèles sont entraînés avec scikit-learn sur les données de la promotion. "
            "Le détail des performances est consultable par votre formateur."
        )
        return "\n\n".join(blocks)

    def _intent_library(self, question: str, c: TutorContext) -> str:
        if c.db is None:
            return None
        from app.services import knowledge_service
        from app.db.models import CourseResource

        rows = list(
            c.db.execute(
                select(CourseResource.category, CourseResource.title, CourseResource.level)
                .order_by(CourseResource.category, CourseResource.title)
            ).all()
        )
        if not rows:
            return ("La bibliothèque de cours est vide pour l'instant. Votre formateur peut y "
                    "ajouter des fiches depuis son espace.")

        by_category: dict[str, list[str]] = {}
        for category, title, level in rows:
            by_category.setdefault(category, []).append(f"{title} ({level})")

        lines = [f"La bibliothèque contient {len(rows)} fiches réparties en "
                 f"{len(by_category)} filières :", ""]
        for category, titles in by_category.items():
            lines.append(f"**{category}**")
            lines.append(_bullets(titles))
            lines.append("")
        lines.append("Posez-moi directement une question sur l'une de ces notions.")
        return "\n".join(lines)

    def _intent_next_step(self, question: str, c: TutorContext) -> str:
        if c.pending_quizzes:
            quiz = c.pending_quizzes[0]
            return (
                f"Votre prochaine étape : passer le quiz « {quiz['title']} »"
                + (f" ({quiz['category']})" if quiz.get("category") else "") + ".\n\n"
                + (f"Il vous reste {len(c.pending_quizzes)} quiz attribués au total.\n\n"
                   if len(c.pending_quizzes) > 1 else "")
                + "Rendez-vous dans « Mes quiz ». La correction est immédiate et votre profil "
                  "est recalculé aussitôt."
            )
        if c.recommendations:
            return (
                f"Votre profil est « {c.profile} ». La première chose à faire est :\n\n"
                f"• {c.recommendations[0]}\n\n"
                + (f"Ensuite : {c.recommendations[1]}.\n\n" if len(c.recommendations) > 1 else "")
                + "Vous pouvez cocher chaque ressource une fois traitée depuis la page "
                  "« Recommandations »."
            )
        return ("Aucun quiz ni recommandation en attente. Lancez une analyse depuis votre tableau "
                "de bord, ou demandez à votre formateur de vous attribuer un quiz.")

    def _intent_satisfaction(self, question: str, c: TutorContext) -> str:
        value = c.metrics.get("satisfaction_score")
        lines = [f"Votre niveau de satisfaction enregistré est de {_fmt(value)}/5."]
        comparison = _compare(value, c.promotion.get("average_satisfaction"), "/5")
        if comparison:
            lines.append(comparison)
        if value is not None and float(value) < 2.5:
            lines += ["", "Une satisfaction basse déclenche automatiquement l'ajout d'un message "
                          "d'accompagnement dans vos recommandations, et signale votre situation "
                          "à votre formateur."]
        return "\n".join(lines)

    def _intent_course_content(self, question: str, c: TutorContext) -> str | None:
        # Traité en amont par la recherche documentaire ; si l'on arrive ici,
        # c'est que la bibliothèque n'a rien trouvé.
        return None

    # --- Repli --------------------------------------------------------------

    def _fallback(self, c: TutorContext) -> str:
        suggestions = [
            "« Quel est mon profil ? »",
            "« Pourquoi ai-je reçu cette recommandation ? »",
            "« Quels quiz dois-je passer ? »",
            "« Quels sont mes points faibles ? »",
            "« Comment m'organiser cette semaine ? »",
            "« Comment je me situe par rapport à la promotion ? »",
        ]
        return (
            "Je n'ai pas trouvé de réponse précise à cette question, ni dans vos données ni dans "
            "la bibliothèque de cours.\n\n"
            "Je suis un moteur à base de règles : je reconnais des sujets par mots-clés et je "
            "cherche dans les fiches de cours. Reformulez avec des termes plus proches du sujet, "
            "ou essayez :\n\n"
            + _bullets(suggestions)
            + "\n\nSi votre question porte sur une notion de cours qui n'est pas encore dans la "
              "bibliothèque, signalez-le à votre formateur : il peut ajouter la fiche "
              "correspondante."
        )


# --- Registre des moteurs ---------------------------------------------------
# Un seul moteur réellement implémenté aujourd'hui. Pour ajouter un LLM :
#   1. créer `class LLMTutorEngine(TutorEngine)` appelant l'API du fournisseur ;
#   2. `register_engine(LLMTutorEngine())` ;
#   3. définir LLM_API_KEY dans backend/.env.
# Tant que ce n'est pas fait, aucune clé n'est requise.
_ENGINES: dict[str, TutorEngine] = {}


def register_engine(engine: TutorEngine) -> None:
    _ENGINES[engine.name] = engine


register_engine(RuleBasedTutorEngine())


def get_engine() -> TutorEngine:
    """Renvoie le moteur actif. Aujourd'hui : toujours le moteur à base de règles."""
    from app.core.config import settings

    if settings.llm_enabled and "llm" in _ENGINES:
        return _ENGINES["llm"]
    return _ENGINES["rules"]


# ---------------------------------------------------------------------------
#  Accès base de données
# ---------------------------------------------------------------------------


def latest_profile(db: Session, learner_id: int) -> LearnerProfile | None:
    return db.execute(
        select(LearnerProfile)
        .where(LearnerProfile.learner_id == learner_id)
        .order_by(LearnerProfile.created_at.desc(), LearnerProfile.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def active_recommendations(db: Session, learner_id: int) -> list[Recommendation]:
    """Recommandations issues de la dernière analyse (même horodatage de lot)."""
    rows = list(
        db.execute(
            select(Recommendation)
            .where(Recommendation.learner_id == learner_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .limit(30)
        ).scalars()
    )
    if not rows:
        return []
    newest = rows[0].created_at
    batch = [r for r in rows if newest is not None and r.created_at == newest]
    return sorted(batch or rows, key=lambda r: r.id)


def promotion_averages(db: Session) -> dict:
    from sqlalchemy import func as sql_func

    row = db.execute(
        select(
            sql_func.count(Learner.id),
            sql_func.avg(Learner.average_score),
            sql_func.avg(Learner.completion_rate),
            sql_func.avg(Learner.satisfaction_score),
            sql_func.avg(Learner.time_spent_hours),
        )
    ).one()
    total, score, completion, satisfaction, time_spent = row
    return {
        "total_learners": int(total or 0),
        "average_score": round(float(score), 1) if score is not None else None,
        "average_completion_rate": round(float(completion), 1) if completion is not None else None,
        "average_satisfaction": round(float(satisfaction), 2) if satisfaction is not None else None,
        "average_time_spent": round(float(time_spent), 1) if time_spent is not None else None,
    }


def build_context(db: Session, learner: Learner) -> TutorContext:
    """Assemble le contexte pédagogique complet d'un apprenant."""
    from app.services import quiz_service  # import tardif : évite un cycle

    profile_row = latest_profile(db, learner.id)
    if profile_row is None:
        profile_row = run_analysis(db, learner)

    recos = active_recommendations(db, learner.id)
    metrics = learner.to_features()
    metrics.update(
        {
            "completed_courses": learner.completed_courses,
            "total_courses": learner.total_courses,
        }
    )

    return TutorContext(
        profile=profile_row.profile,
        metrics=metrics,
        recommendations=[r.content for r in recos],
        reason=recos[0].reason if recos else None,
        risk_level=profile_row.risk_level,
        cluster=profile_row.cluster,
        confidence=profile_row.confidence,
        explanation=profile_row.explanation,
        category=learner.course_category,
        student_id=learner.student_id,
        name=learner.display_name,
        quiz_summary=quiz_service.learner_quiz_summary(db, learner.id),
        pending_quizzes=quiz_service.pending_assignments(db, learner.id),
        promotion=promotion_averages(db),
        db=db,
    )


def run_analysis(db: Session, learner: Learner, persist_recommendations: bool = True) -> LearnerProfile:
    """Exécute la chaîne ML complète et enregistre le résultat.

    Apprenant → prétraitement → K-Means + Decision Tree → profil →
    moteur de recommandation → persistance.
    """
    features = learner.to_features()
    analysis = analyze_profile(features)

    profile_row = LearnerProfile(
        learner_id=learner.id,
        profile=analysis["profile"],
        cluster=analysis.get("cluster"),
        confidence=analysis.get("confidence"),
        risk_level=analysis.get("risk_level"),
        explanation=analysis.get("explanation"),
        source=analysis.get("source", "model"),
    )
    db.add(profile_row)
    db.flush()

    if persist_recommendations:
        reco = recommend_content(
            profile=analysis["profile"],
            average_score=features["average_score"],
            completion_rate=features["completion_rate"],
            failed_quizzes=features["failed_quizzes"],
            satisfaction_score=features["satisfaction_score"],
        )
        created = dt.datetime.now(dt.timezone.utc)
        for content in reco["recommended_content"]:
            db.add(
                Recommendation(
                    learner_id=learner.id,
                    content=content,
                    reason=reco["reason"],
                    priority=reco["priority"],
                    profile=analysis["profile"],
                    created_at=created,
                )
            )

    db.commit()
    db.refresh(profile_row)
    return profile_row


def ask(db: Session, learner: Learner, question: str) -> dict:
    """Pose une question au tuteur et enregistre l'échange dans l'historique."""
    question = (question or "").strip()
    if not question:
        raise EmptyQuestionError("La question ne peut pas être vide.")
    if len(question) > MAX_QUESTION_LENGTH:
        question = question[:MAX_QUESTION_LENGTH]

    context = build_context(db, learner)
    engine = get_engine()
    answer_text = engine.answer(question, context)

    db.add(ChatMessage(learner_id=learner.id, role="user", message=question))
    db.add(ChatMessage(learner_id=learner.id, role="assistant", message=answer_text))
    db.commit()

    return {
        "answer": answer_text,
        "profile": context.profile,
        "engine": engine.name,
        "engine_label": engine.label,
    }


def chat_history(db: Session, learner_id: int, limit: int = 200) -> list[ChatMessage]:
    rows = list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.learner_id == learner_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        ).scalars()
    )
    return sorted(rows, key=lambda m: (m.created_at, m.id))


def clear_history(db: Session, learner_id: int) -> int:
    result = db.execute(delete(ChatMessage).where(ChatMessage.learner_id == learner_id))
    db.commit()
    return int(result.rowcount or 0)
