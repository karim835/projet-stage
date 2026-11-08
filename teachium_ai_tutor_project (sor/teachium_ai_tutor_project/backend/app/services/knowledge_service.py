"""Recherche dans la bibliothèque de cours (base de connaissances de l'AI Tutor).

Le tuteur doit pouvoir répondre à des questions portant sur le **contenu des
cours**, pas seulement sur les indicateurs de l'apprenant. Ce module indexe les
fiches de la table `course_resources` et retrouve la plus pertinente pour une
question donnée.

Méthode : **TF-IDF + similarité cosinus** (scikit-learn, déjà utilisé par le
projet). Chaque fiche devient un vecteur de poids de mots ; la question est
projetée dans le même espace et l'on retient les fiches les plus proches.

Ce n'est pas de la compréhension sémantique : c'est de la recherche
d'information statistique. Le tuteur cite donc toujours la fiche source, ce qui
permet à l'apprenant de vérifier l'origine de la réponse.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CourseResource

#: Bonus appliqué au score d'une fiche de la filière de l'apprenant.
CATEGORY_BOOST = 1.3

# Mots vides français : scikit-learn n'en fournit que pour l'anglais.
FRENCH_STOPWORDS = {
    "a", "afin", "ai", "aime", "ainsi", "alors", "au", "aucun", "aujourd", "auquel", "aussi",
    "autre", "autres", "aux", "avait", "avant", "avec", "avoir", "bah", "beaucoup", "bien",
    "bon", "car", "ce", "cela", "celle", "celles", "celui", "cependant", "certain", "certains",
    "ces", "cet", "cette", "ceux", "chaque", "chez", "combien", "comme", "comment", "concernant",
    "dans", "de", "dedans", "dehors", "depuis", "des", "desormais", "deux", "devrait", "doit",
    "donc", "dont", "du", "duquel", "durant", "elle", "elles", "en", "encore", "entre", "envers",
    "est", "et", "etait", "etc", "ete", "etre", "eu", "faire", "fais", "fait", "faites", "faut",
    "il", "ils", "je", "juste", "la", "laquelle", "le", "lequel", "les", "leur", "leurs", "lors",
    "lui", "ma", "mais", "malgre", "me", "meme", "mes", "moi", "moins", "mon", "ne", "ni", "non",
    "nos", "notre", "nous", "on", "ont", "ou", "par", "parce", "parfois", "pas", "pendant",
    "peut", "peux", "plus", "plusieurs", "plutot", "por", "pour", "pourquoi", "puis", "qu",
    "quand", "que", "quel", "quelle", "quelles", "quels", "qui", "quoi", "sa", "sans", "se",
    "sera", "ses", "seulement", "si", "sien", "soi", "soit", "son", "sont", "sous", "sur", "ta",
    "tandis", "tant", "te", "tes", "toi", "ton", "tous", "tout", "toute", "toutes", "tres", "tu",
    "un", "une", "va", "vers", "voici", "voila", "vos", "votre", "vous", "y", "etais", "serait",
    "suis", "sommes", "avez", "avons", "peut-etre", "donne", "donner", "explique", "expliquer",
    "dis", "dire", "veux", "vouloir", "sais", "savoir", "connais", "connaitre",
}


def strip_accents(text: str) -> str:
    """Supprime les accents : « complétion » et « completion » deviennent identiques."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    return strip_accents((text or "").lower())


def light_stem(word: str) -> str:
    """Racinisation minimale du français : neutralise surtout les pluriels.

    Volontairement prudente — on ne cherche pas un vrai stemmer, seulement à
    éviter que « boucle » et « boucles » soient traités comme deux mots sans
    rapport lors de la recherche.
    """
    if len(word) > 4 and word.endswith("aux"):
        return word[:-3] + "al"
    if len(word) > 4 and word.endswith("ses"):
        return word[:-2]
    if len(word) > 3 and word[-1] in {"s", "x"}:
        return word[:-1]
    return word


def french_tokenizer(text: str) -> list[str]:
    """Découpe en mots normalisés, sans accents ni mots vides, avec racinisation."""
    words = re.findall(r"[a-z0-9_+#]{2,}", normalize(text))
    return [light_stem(w) for w in words if w not in FRENCH_STOPWORDS]


class _Index:
    """Index TF-IDF construit paresseusement et invalidé au moindre changement."""

    def __init__(self) -> None:
        self.signature: tuple | None = None
        self.vectorizer = None
        self.matrix = None
        self.resources: list[CourseResource] = []

    def build(self, resources: list[CourseResource], signature: tuple) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.resources = resources
        self.signature = signature
        if not resources:
            self.vectorizer = None
            self.matrix = None
            return

        self.vectorizer = TfidfVectorizer(
            tokenizer=french_tokenizer,
            preprocessor=lambda x: x,
            lowercase=False,
            token_pattern=None,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
        )
        self.matrix = self.vectorizer.fit_transform([r.searchable_text() for r in resources])


_index = _Index()


def _signature(db: Session) -> tuple:
    """Empreinte du contenu : (nombre de fiches, dernière modification)."""
    row = db.execute(
        select(func.count(CourseResource.id), func.max(CourseResource.updated_at))
    ).one()
    return (int(row[0] or 0), str(row[1]))


def invalidate() -> None:
    """Force la reconstruction de l'index (appelé après une écriture)."""
    _index.signature = None


def _ensure_index(db: Session) -> None:
    signature = _signature(db)
    if _index.signature == signature:
        return
    resources = list(db.execute(select(CourseResource).order_by(CourseResource.id)).scalars())
    _index.build(resources, signature)


def search(db: Session, query: str, top_k: int = 3, category: str | None = None) -> list[dict]:
    """Retourne les fiches les plus proches de la question, avec leur score.

    Le score est une similarité cosinus entre 0 et 1. Un score faible signifie
    que la bibliothèque ne contient probablement pas la réponse : l'appelant
    doit alors le dire honnêtement plutôt que d'inventer.
    """
    query = (query or "").strip()
    if not query:
        return []

    _ensure_index(db)
    if _index.matrix is None or not _index.resources:
        return []

    from sklearn.metrics.pairwise import cosine_similarity

    try:
        vector = _index.vectorizer.transform([query])
    except ValueError:
        return []

    scores = cosine_similarity(vector, _index.matrix)[0]

    ranked = sorted(
        (
            {"resource": resource, "score": float(score)}
            for resource, score in zip(_index.resources, scores)
            if score > 0
        ),
        key=lambda item: item["score"],
        reverse=True,
    )

    if category:
        # Bonus multiplicatif : à pertinence comparable, une fiche de la filière de
        # l'apprenant passe devant. Le bonus ne doit jamais faire remonter une fiche
        # hors sujet devant une fiche nettement plus pertinente, d'où un facteur
        # modéré appliqué au score plutôt qu'un tri par catégorie.
        for item in ranked:
            if item["resource"].category == category:
                item["score"] *= CATEGORY_BOOST
        ranked.sort(key=lambda item: item["score"], reverse=True)

    return ranked[:top_k]


def best_passage(resource: CourseResource, query: str, max_chars: int = 600) -> str:
    """Extrait le paragraphe de la fiche le plus proche de la question.

    Évite de renvoyer une fiche entière quand seule une section est pertinente.
    """
    content = resource.content or ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not paragraphs:
        return content[:max_chars]

    query_terms = set(french_tokenizer(query))
    if not query_terms:
        return paragraphs[0][:max_chars]

    def relevance(paragraph: str) -> float:
        terms = french_tokenizer(paragraph)
        if not terms:
            return 0.0
        hits = sum(1 for t in terms if t in query_terms)
        # Normalisation douce : un paragraphe long n'est pas avantagé mécaniquement.
        return hits / (len(terms) ** 0.5)

    best = max(paragraphs, key=relevance)
    if relevance(best) == 0:
        best = paragraphs[0]

    if len(best) <= max_chars:
        # On complète avec le paragraphe suivant si la place le permet.
        index = paragraphs.index(best)
        if index + 1 < len(paragraphs) and len(best) + len(paragraphs[index + 1]) + 2 <= max_chars:
            return f"{best}\n\n{paragraphs[index + 1]}"
        return best

    truncated = best[:max_chars]
    cut = truncated.rfind(". ")
    return (truncated[: cut + 1] if cut > max_chars * 0.5 else truncated.rstrip()) + " […]"


def categories(db: Session) -> list[str]:
    return [
        row for row in db.execute(
            select(CourseResource.category).distinct().order_by(CourseResource.category)
        ).scalars()
    ]
