"""Remplit la bibliothèque de cours et crée des quiz de démonstration.

    python scripts/seed_content.py [--reset]

Le script est idempotent : il n'insère une fiche ou un quiz que s'il n'existe
pas déjà (identifié par son titre). `--reset` supprime d'abord les fiches et
quiz créés par ce script.

Les fiches de cours sont du contenu pédagogique réel : elles constituent la
base de connaissances interrogée par l'AI Tutor (recherche TF-IDF).
"""

from __future__ import annotations

import argparse

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select

from app.core.config import settings
from app.db.database import check_connection, create_all, session_scope
from app.db.models import (
    ROLE_ADMIN,
    ROLE_TRAINER,
    CourseResource,
    Learner,
    Quiz,
    QuizQuestion,
    User,
)
from app.services import knowledge_service, quiz_service

# ===========================================================================
#  Bibliothèque de cours
# ===========================================================================

COURSES: list[dict] = [
    # ---------------------------------------------------------------- Python
    {
        "title": "Les variables et les types en Python",
        "category": "Python",
        "level": "Débutant",
        "keywords": "variable, type, int, float, str, bool, affectation, conversion, cast",
        "summary": "Comment stocker une valeur, quels types existent et comment passer de l'un à l'autre.",
        "content": """Une variable est un nom qui désigne une valeur en mémoire. En Python, on crée une variable simplement en lui affectant une valeur avec le signe égal : age = 25. Il n'y a pas de déclaration de type préalable, contrairement au Java ou au C.

Python possède quatre types de base. Le type int représente les nombres entiers (10, -3, 1000). Le type float représente les nombres décimaux (3.14, -0.5). Le type str représente le texte, écrit entre guillemets simples ou doubles ("bonjour"). Le type bool ne peut prendre que deux valeurs : True ou False.

La fonction type() indique le type d'une valeur : type(25) renvoie int. La conversion entre types s'appelle le transtypage. int("42") transforme la chaîne "42" en nombre 42. str(42) fait l'inverse. float("3.14") produit un nombre décimal. Attention : int("bonjour") provoque une erreur ValueError, car le texte ne représente pas un nombre.

Une erreur fréquente chez les débutants consiste à additionner un nombre et une chaîne : 5 + "3" échoue. Il faut convertir explicitement : 5 + int("3") donne 8, tandis que str(5) + "3" donne la chaîne "53".

Les noms de variables suivent des règles : ils commencent par une lettre ou un underscore, ne contiennent ni espace ni accent, et ne peuvent pas être un mot réservé du langage comme if, for ou class. La convention en Python est le snake_case : score_moyen plutôt que scoreMoyen.""",
    },
    {
        "title": "Les boucles for et while en Python",
        "category": "Python",
        "level": "Débutant",
        "keywords": "boucle, for, while, range, itération, break, continue, parcours",
        "summary": "Répéter des instructions : différence entre for et while, et pièges classiques.",
        "content": """Une boucle répète un bloc d'instructions. Python en propose deux formes, qui répondent à des besoins différents.

La boucle for parcourt les éléments d'une séquence. On l'utilise quand on sait sur quoi itérer : for lettre in "python" parcourt chaque caractère, for note in notes parcourt chaque élément d'une liste. La fonction range() génère une suite de nombres : range(5) produit 0, 1, 2, 3, 4. Attention, la borne finale est exclue. range(1, 6) produit 1 à 5, et range(0, 10, 2) produit les nombres pairs de 0 à 8.

La boucle while répète tant qu'une condition reste vraie. On l'utilise quand on ne sait pas à l'avance combien de tours seront nécessaires, par exemple pour redemander une saisie tant qu'elle est invalide. Le danger est la boucle infinie : si la condition ne devient jamais fausse, le programme ne s'arrête plus. Il faut toujours vérifier qu'une variable évolue à l'intérieur de la boucle.

Deux instructions modifient le déroulement d'une boucle. break interrompt immédiatement la boucle et passe à la suite du programme. continue saute le reste du tour courant et passe directement au tour suivant.

L'erreur la plus fréquente concerne l'indentation. En Python, c'est l'indentation qui délimite le corps de la boucle, pas des accolades. Une ligne mal indentée sort du bloc et ne sera exécutée qu'une seule fois, après la boucle.

Pour parcourir une liste avec l'indice et la valeur, enumerate() est préférable à range(len(liste)) : for i, valeur in enumerate(notes) est plus lisible et moins sujet aux erreurs de borne.""",
    },
    {
        "title": "Les listes et dictionnaires Python",
        "category": "Python",
        "level": "Intermédiaire",
        "keywords": "liste, dictionnaire, dict, append, clé, valeur, compréhension, index, tuple",
        "summary": "Les deux structures de données les plus utilisées, et quand choisir l'une ou l'autre.",
        "content": """La liste est une séquence ordonnée et modifiable, écrite entre crochets : notes = [12, 15, 8]. On accède à un élément par son indice, en commençant à zéro : notes[0] vaut 12. Les indices négatifs partent de la fin : notes[-1] vaut 8. append() ajoute un élément à la fin, remove() supprime la première occurrence d'une valeur, len() donne la taille.

Le dictionnaire associe des clés à des valeurs, entre accolades : apprenant = {"nom": "Sara", "score": 78}. On accède à une valeur par sa clé et non par un indice : apprenant["score"] vaut 78. Une clé absente provoque une KeyError ; la méthode get() évite ce problème en renvoyant None ou une valeur par défaut : apprenant.get("email", "non renseigné").

Le choix entre les deux dépend de la façon dont on cherche l'information. Si l'on parcourt tous les éléments dans l'ordre, la liste convient. Si l'on cherche un élément par un identifiant, le dictionnaire est bien plus rapide : la recherche est immédiate quelle que soit la taille, alors qu'une liste doit être parcourue élément par élément.

La compréhension de liste permet de construire une liste en une ligne : [n * 2 for n in notes] double chaque note, et [n for n in notes if n >= 10] ne conserve que les notes supérieures ou égales à 10. C'est plus concis et plus rapide qu'une boucle avec append().

Le tuple ressemble à une liste mais s'écrit entre parenthèses et n'est pas modifiable. On l'utilise pour des données qui ne doivent pas changer, comme des coordonnées.

Un piège classique : deux variables qui pointent vers la même liste partagent le même objet. b = a ne copie pas la liste ; modifier b modifie aussi a. Pour copier réellement, il faut écrire b = a.copy() ou b = list(a).""",
    },
    {
        "title": "Fonctions et gestion des erreurs en Python",
        "category": "Python",
        "level": "Intermédiaire",
        "keywords": "fonction, def, return, paramètre, argument, exception, try, except, portée",
        "summary": "Découper son code en fonctions et gérer proprement les cas d'erreur.",
        "content": """Une fonction regroupe des instructions sous un nom, pour les réutiliser sans les recopier. On la définit avec def : def moyenne(notes): puis, dans le corps indenté, return sum(notes) / len(notes).

Les paramètres sont les noms déclarés dans la définition ; les arguments sont les valeurs passées à l'appel. Un paramètre peut avoir une valeur par défaut : def saluer(nom, message="Bonjour"). Les paramètres avec valeur par défaut doivent figurer après ceux qui n'en ont pas.

L'instruction return renvoie une valeur et termine immédiatement la fonction. Une fonction sans return renvoie None. Confondre print et return est une erreur très répandue : print affiche à l'écran mais ne rend rien d'exploitable, return fournit une valeur que l'appelant peut stocker et réutiliser.

La portée des variables est locale par défaut : une variable créée dans une fonction n'existe pas à l'extérieur. C'est une protection, pas une contrainte : elle évite qu'une fonction modifie par accident des données du reste du programme.

La gestion des erreurs repose sur le bloc try/except. On place dans try le code susceptible d'échouer, et dans except le traitement de l'erreur. Il faut toujours préciser le type d'exception attendu : except ValueError plutôt qu'un except nu, qui masquerait aussi les erreurs de programmation. Le bloc finally s'exécute dans tous les cas, avec ou sans erreur, et sert typiquement à libérer une ressource.

Une bonne fonction fait une seule chose, tient sur une vingtaine de lignes au maximum, et porte un nom qui décrit ce qu'elle renvoie.""",
    },
    # ------------------------------------------------------------------ Data
    {
        "title": "Introduction à l'analyse de données avec pandas",
        "category": "Data",
        "level": "Débutant",
        "keywords": "pandas, dataframe, csv, colonne, ligne, filtrage, groupby, analyse",
        "summary": "Charger, explorer et filtrer un jeu de données tabulaire.",
        "content": """pandas est la bibliothèque Python de référence pour manipuler des données tabulaires. Sa structure centrale est le DataFrame : un tableau à deux dimensions, avec des colonnes nommées et typées, comparable à une feuille de calcul.

Le chargement d'un fichier se fait en une ligne : df = pd.read_csv("donnees.csv"). Les premières vérifications sont toujours les mêmes. df.head() affiche les cinq premières lignes. df.shape donne le nombre de lignes et de colonnes. df.info() liste les colonnes, leur type et le nombre de valeurs manquantes. df.describe() produit les statistiques descriptives des colonnes numériques : moyenne, écart-type, minimum, quartiles, maximum.

La sélection d'une colonne s'écrit df["score"], celle de plusieurs colonnes df[["score", "temps"]] avec une double paire de crochets. Le filtrage utilise une condition booléenne : df[df["score"] < 50] ne conserve que les lignes dont le score est inférieur à 50. Plusieurs conditions se combinent avec & pour "et" et | pour "ou", chaque condition devant être entourée de parenthèses.

L'agrégation par groupe est l'opération la plus utile en analyse. df.groupby("profil")["score"].mean() calcule le score moyen pour chaque profil. On peut agréger plusieurs colonnes et plusieurs fonctions à la fois avec agg().

Les valeurs manquantes se détectent avec df.isna().sum(), qui compte les trous par colonne. Deux stratégies existent : supprimer les lignes concernées avec dropna(), ou les remplacer avec fillna(). Le choix dépend du volume de données perdues et de la nature de la variable ; supprimer 40 % des lignes pour combler une colonne secondaire est rarement le bon arbitrage.""",
    },
    {
        "title": "Comprendre le clustering et l'algorithme K-Means",
        "category": "Data",
        "level": "Intermédiaire",
        "keywords": "clustering, k-means, kmeans, non supervisé, groupe, centroïde, elbow, normalisation",
        "summary": "Regrouper automatiquement des individus similaires sans connaître les catégories à l'avance.",
        "content": """Le clustering est une technique d'apprentissage non supervisé : on cherche à regrouper des individus semblables sans disposer d'étiquettes préexistantes. C'est la différence fondamentale avec la classification, où les catégories sont connues et fournies pendant l'entraînement.

K-Means est l'algorithme de clustering le plus répandu. Son principe est itératif. On choisit d'abord un nombre k de groupes. L'algorithme place k centres au hasard, rattache chaque individu au centre le plus proche, recalcule chaque centre comme la moyenne des individus qui lui sont rattachés, puis recommence. Le processus s'arrête quand les centres ne bougent plus.

La normalisation des données est indispensable avant d'appliquer K-Means. L'algorithme raisonne en distances : sans mise à l'échelle, une variable exprimée en heures (de 0 à 40) écraserait complètement une variable exprimée de 1 à 5. Le StandardScaler de scikit-learn ramène chaque variable à une moyenne de zéro et un écart-type de un.

Le choix de k n'est pas automatique. La méthode du coude consiste à tracer l'inertie, c'est-à-dire la somme des distances au centre de chaque groupe, en fonction de k. Cette inertie diminue toujours quand k augmente ; on retient la valeur où la courbe se casse nettement, car au-delà le gain devient marginal.

K-Means a des limites qu'il faut connaître. Il suppose des groupes de forme sphérique et de taille comparable. Il est sensible à l'initialisation, raison pour laquelle on lance plusieurs essais avec n_init. Enfin, il attribue toujours chaque individu à un groupe, même quand celui-ci est atypique : il ne détecte pas les valeurs aberrantes.

L'interprétation des groupes reste un travail humain. L'algorithme produit des numéros de cluster ; c'est l'analyste qui, en examinant les moyennes de chaque groupe, leur donne un nom pédagogique comme « apprenants en difficulté » ou « apprenants avancés ».""",
    },
    {
        "title": "Arbres de décision et classification supervisée",
        "category": "Data",
        "level": "Intermédiaire",
        "keywords": "arbre de décision, classification, supervisé, entraînement, test, surapprentissage, profondeur",
        "summary": "Prédire une catégorie à partir d'exemples étiquetés, avec un modèle explicable.",
        "content": """La classification supervisée consiste à prédire une catégorie à partir d'exemples déjà étiquetés. On dispose d'un jeu de données où la bonne réponse est connue, et le modèle apprend à la reproduire sur des cas nouveaux.

L'arbre de décision apprend une cascade de questions. Chaque nœud pose un test sur une variable, par exemple « le score moyen est-il inférieur à 50 ? ». Selon la réponse, on descend à gauche ou à droite, jusqu'à atteindre une feuille qui donne la catégorie prédite. L'algorithme choisit à chaque nœud la question qui sépare le mieux les classes, en s'appuyant sur une mesure d'impureté comme l'indice de Gini ou l'entropie.

Le grand atout de l'arbre est son explicabilité. On peut afficher le chemin exact qui a mené à une décision, ce qui est décisif dans un contexte pédagogique ou réglementaire : on peut justifier auprès d'un formateur pourquoi tel apprenant a été classé « en difficulté ».

La séparation entraînement/test est une règle absolue. On entraîne le modèle sur environ 75 % des données et on l'évalue sur les 25 % restants, qu'il n'a jamais vus. Évaluer un modèle sur ses données d'entraînement donne des chiffres flatteurs et faux.

Le surapprentissage est le principal risque des arbres. Un arbre laissé libre finit par créer une feuille par exemple : il obtient 100 % sur l'entraînement et s'effondre sur des données nouvelles, car il a mémorisé le bruit au lieu d'apprendre la règle. On le limite en fixant une profondeur maximale, un nombre minimal d'exemples par feuille, ou en élaguant l'arbre.

Quand les classes sont déséquilibrées, le paramètre class_weight="balanced" donne plus de poids aux classes rares. Sans lui, un modèle peut atteindre 90 % d'exactitude en ignorant totalement une classe minoritaire, ce qui est inutile en pratique.""",
    },
    {
        "title": "Évaluer un modèle : accuracy, précision, rappel et F1",
        "category": "Data",
        "level": "Avancé",
        "keywords": "évaluation, accuracy, exactitude, précision, rappel, recall, f1, matrice de confusion",
        "summary": "Quatre indicateurs pour juger un modèle de classification, et quand chacun compte.",
        "content": """L'exactitude, ou accuracy, est le pourcentage de prédictions correctes sur l'ensemble des cas. C'est l'indicateur le plus intuitif, mais il devient trompeur dès que les classes sont déséquilibrées. Si 95 % des apprenants réussissent, un modèle qui prédit toujours « réussite » obtient 95 % d'exactitude sans avoir rien appris d'utile.

La précision répond à la question : parmi les cas que le modèle a classés dans une catégorie, quelle proportion l'était réellement ? Une précision faible signifie beaucoup de fausses alertes. Si l'on annonce à vingt apprenants qu'ils sont en difficulté alors que seuls dix le sont, la précision est de 50 %.

Le rappel, ou recall, répond à la question inverse : parmi les cas qui appartiennent réellement à une catégorie, quelle proportion le modèle a-t-il détectée ? Un rappel faible signifie que l'on passe à côté de vrais cas. Détecter huit apprenants en difficulté sur dix donne un rappel de 80 %.

Précision et rappel s'opposent généralement. Un modèle très prudent, qui ne signale que les cas évidents, aura une bonne précision et un rappel médiocre. Un modèle alarmiste aura l'inverse. Le F1-score est la moyenne harmonique des deux : il ne devient élevé que si les deux le sont, ce qui en fait un bon indicateur de synthèse.

Le choix de l'indicateur prioritaire dépend du coût des erreurs. Pour repérer des apprenants en décrochage, le rappel prime : mieux vaut alerter à tort que laisser quelqu'un décrocher sans réagir. Pour une décision coûteuse ou irréversible, la précision prime.

La matrice de confusion croise les catégories réelles et prédites. Sa diagonale contient les bonnes prédictions ; les cases hors diagonale montrent exactement quelles catégories le modèle confond. C'est l'outil le plus informatif pour comprendre où un modèle échoue.

Les moyennes pondérées, calculées en tenant compte de l'effectif de chaque classe, donnent une vue d'ensemble sur un problème à plusieurs catégories.""",
    },
    # ------------------------------------------------------------------- Web
    {
        "title": "HTML et CSS : structure et présentation",
        "category": "Web",
        "level": "Débutant",
        "keywords": "html, css, balise, sélecteur, flexbox, responsive, sémantique, classe",
        "summary": "Séparer le contenu de sa présentation, et construire une mise en page moderne.",
        "content": """HTML décrit la structure et le sens d'une page ; CSS décrit son apparence. Cette séparation est le principe fondateur du web : le même contenu peut être présenté différemment selon l'écran, sans être réécrit.

Une balise HTML entoure un contenu et lui donne un sens. Les balises sémantiques doivent être préférées aux div génériques : header pour l'en-tête, nav pour la navigation, main pour le contenu principal, article pour un contenu autonome, footer pour le pied de page. Cette sémantique est utilisée par les lecteurs d'écran et par les moteurs de recherche : ce n'est pas une préférence de style.

CSS applique des règles à des éléments sélectionnés. Un sélecteur de classe s'écrit .carte et cible tous les éléments portant class="carte". Un sélecteur d'identifiant s'écrit #menu. En cas de conflit, la règle la plus spécifique gagne ; à spécificité égale, la dernière déclarée l'emporte.

Le modèle de boîte régit les dimensions. Chaque élément est une boîte composée du contenu, du padding intérieur, de la bordure et de la marge extérieure. Par défaut, la largeur déclarée ne concerne que le contenu, ce qui rend les calculs pénibles. La règle box-sizing: border-box inclut padding et bordure dans la largeur : elle est appliquée systématiquement dans les projets modernes.

Flexbox organise les éléments sur une ligne ou une colonne. display: flex sur le conteneur, puis justify-content pour l'alignement dans l'axe principal et align-items pour l'axe perpendiculaire. CSS Grid, plus adapté aux mises en page à deux dimensions, complète Flexbox plutôt qu'il ne le remplace.

Le responsive design adapte la page à la taille de l'écran. Les media queries appliquent des règles conditionnelles : @media (max-width: 768px) cible les écrans étroits. L'approche mobile-first consiste à écrire d'abord les styles pour petit écran, puis à les enrichir pour les grands.""",
    },
    {
        "title": "Les bases de React : composants, props et état",
        "category": "Web",
        "level": "Intermédiaire",
        "keywords": "react, composant, props, state, usestate, useeffect, jsx, hook, rendu",
        "summary": "Construire une interface à partir de composants réutilisables qui réagissent aux données.",
        "content": """React construit une interface à partir de composants : des fonctions JavaScript qui reçoivent des données et renvoient du JSX, une syntaxe proche du HTML. Un composant doit avoir un nom commençant par une majuscule, sans quoi React le traite comme une balise HTML ordinaire.

Les props sont les données passées d'un composant parent vers un enfant. Elles sont en lecture seule : un composant ne modifie jamais ses propres props. Ce flux descendant et unidirectionnel rend le comportement prévisible, car on sait toujours d'où vient une donnée.

L'état, géré par le hook useState, contient les données qui changent au cours de la vie du composant. const [valeur, setValeur] = useState(0) déclare un état et sa fonction de mise à jour. Modifier directement la variable ne déclenche aucun rendu : il faut impérativement passer par la fonction setValeur. Quand la nouvelle valeur dépend de l'ancienne, la forme fonctionnelle est plus sûre : setValeur(v => v + 1).

Le hook useEffect exécute du code après le rendu, typiquement pour appeler une API. Son tableau de dépendances détermine quand il se relance : un tableau vide signifie une seule exécution au montage ; un tableau contenant des variables signifie une relance à chaque changement de ces variables. Omettre le tableau relance l'effet à chaque rendu, ce qui provoque souvent une boucle infinie d'appels réseau.

Le rendu de liste exige une prop key unique et stable sur chaque élément. Utiliser l'indice du tableau comme clé pose problème dès que la liste est réordonnée ou filtrée : React réutilise alors le mauvais élément. L'identifiant issu des données est toujours préférable.

Les règles des hooks sont strictes : ils doivent être appelés au niveau supérieur du composant, jamais dans une condition ni dans une boucle. React s'appuie sur l'ordre des appels pour associer chaque hook à son état.""",
    },
    {
        "title": "API REST : principes et bonnes pratiques",
        "category": "Web",
        "level": "Intermédiaire",
        "keywords": "api, rest, http, get, post, put, delete, json, statut, endpoint, authentification",
        "summary": "Concevoir une interface entre client et serveur : verbes, ressources et codes de statut.",
        "content": """Une API REST expose des ressources identifiées par des URL, manipulées à l'aide des verbes du protocole HTTP. La ressource est un nom, généralement au pluriel : /api/apprenants. L'action est portée par le verbe, jamais par l'URL. On écrit donc GET /api/apprenants et non GET /api/getApprenants.

Chaque verbe a une sémantique précise. GET lit sans rien modifier. POST crée une ressource. PUT remplace intégralement une ressource existante. PATCH en modifie seulement certains champs. DELETE la supprime. GET, PUT et DELETE sont idempotents : les répéter produit le même résultat final. POST ne l'est pas, ce qui explique les doublons créés par un double clic sur un bouton de validation.

Les codes de statut informent le client sans qu'il ait à interpréter le corps de la réponse. La famille 2xx signale un succès : 200 pour une lecture, 201 pour une création, 204 pour une suppression sans contenu. La famille 4xx signale une erreur du client : 400 requête mal formée, 401 non authentifié, 403 authentifié mais sans les droits, 404 ressource inexistante, 409 conflit, 422 données invalides. La famille 5xx signale une défaillance du serveur.

La distinction entre 401 et 403 est souvent mal comprise. 401 signifie « je ne sais pas qui vous êtes » ; 403 signifie « je sais qui vous êtes, et vous n'avez pas le droit ».

L'authentification par jeton JWT est la plus répandue pour une API consommée par une application web. Le serveur renvoie à la connexion un jeton signé contenant l'identifiant et le rôle. Le client le joint ensuite à chaque requête dans l'en-tête Authorization. La signature empêche toute falsification : modifier le rôle dans le jeton l'invalide.

Les contrôles de droits doivent toujours être effectués côté serveur. Masquer un bouton dans l'interface n'est pas une sécurité : n'importe qui peut appeler l'API directement.""",
    },
    # ------------------------------------------------------------ Management
    {
        "title": "Gestion de projet : cycle en V et méthodes agiles",
        "category": "Management",
        "level": "Débutant",
        "keywords": "gestion de projet, agile, scrum, cycle en v, sprint, backlog, planification, cahier des charges",
        "summary": "Deux approches d'organisation d'un projet, et les critères pour choisir.",
        "content": """Le cycle en V organise un projet en phases successives : recueil des besoins, spécifications, conception, développement, puis remontée des tests jusqu'à la recette. Chaque phase de descente a sa phase de validation symétrique. Ce modèle convient aux projets dont les besoins sont stables et bien connus dès le départ, et aux contextes réglementés où la traçabilité prime.

Sa faiblesse est la rigidité. Le client ne voit un résultat concret qu'à la fin, et tout changement de besoin en cours de route coûte cher car il remet en cause les phases déjà validées.

Les méthodes agiles procèdent par itérations courtes, appelées sprints, généralement de deux à quatre semaines. Chaque sprint produit un incrément utilisable du produit. Le client voit un résultat régulièrement et peut réorienter le travail.

Scrum est le cadre agile le plus répandu. Il définit trois rôles. Le Product Owner porte la vision et priorise le backlog, la liste ordonnée de tout ce qui reste à faire. Le Scrum Master facilite le travail et lève les obstacles. L'équipe de développement réalise l'incrément. Quatre rituels rythment le sprint : la planification au début, la mêlée quotidienne de quinze minutes, la revue de fin de sprint avec le client, et la rétrospective où l'équipe améliore sa propre façon de travailler.

Le choix entre les deux approches dépend de la stabilité du besoin, pas d'une mode. Un besoin figé et contractuel oriente vers le cycle en V ; un besoin qui se précise au fil des retours oriente vers l'agilité. Beaucoup d'organisations pratiquent une forme hybride : un cadrage initial structuré, puis une réalisation itérative.

L'erreur courante consiste à adopter les rituels agiles sans en adopter l'esprit : faire des mêlées quotidiennes tout en maintenant un plan figé sur douze mois produit la lourdeur des deux approches et les bénéfices d'aucune.""",
    },
    {
        "title": "Animer une équipe et conduire une réunion efficace",
        "category": "Management",
        "level": "Intermédiaire",
        "keywords": "équipe, réunion, animation, ordre du jour, décision, délégation, feedback, motivation",
        "summary": "Structurer une réunion utile et déléguer sans perdre le contrôle.",
        "content": """Une réunion utile commence avant la réunion. Trois éléments doivent être fixés et diffusés à l'avance : l'objectif, formulé comme une décision à prendre ou un problème à résoudre ; l'ordre du jour avec un temps alloué à chaque point ; et la liste des participants réellement nécessaires. Une personne qui n'a rien à décider ni à apporter n'a pas besoin d'être présente ; un compte rendu lui suffit.

Pendant la réunion, l'animateur veille au temps, distribue la parole et recentre les échanges. Les sujets qui débordent sont notés pour être traités séparément plutôt que d'absorber le temps commun. Un point utile se termine par une décision explicite ou par une action assignée.

Une action sans propriétaire nommé et sans échéance n'est pas une action, c'est une intention. Le compte rendu doit tenir en quelques lignes : décisions prises, actions avec responsable et date, points reportés.

La délégation ne consiste pas à distribuer des tâches mais à transférer une responsabilité avec la marge de manœuvre correspondante. Elle suppose de définir clairement le résultat attendu et les contraintes, puis de laisser la personne choisir sa méthode. Déléguer en imposant chaque étape n'est pas de la délégation mais de l'exécution supervisée, et cela n'apporte ni gain de temps ni développement des compétences.

Le retour, ou feedback, est plus efficace quand il est rapide, factuel et centré sur le comportement plutôt que sur la personne. Décrire un fait précis, expliquer son effet concret, puis convenir de ce qui change à l'avenir est plus utile qu'un jugement général.

La motivation d'une équipe repose davantage sur l'autonomie, la clarté du sens et la reconnaissance du travail accompli que sur des dispositifs incitatifs ponctuels.""",
    },
    # --------------------------------------------------------- Communication
    {
        "title": "Communication professionnelle écrite",
        "category": "Communication",
        "level": "Débutant",
        "keywords": "communication, écrit, e-mail, courriel, message, clarté, structure, ton, rédaction",
        "summary": "Écrire des messages professionnels clairs, lus et compris du premier coup.",
        "content": """Un message professionnel efficace répond à trois questions dès les premières lignes : de quoi s'agit-il, qu'attend-on du destinataire, et pour quand. Le lecteur doit pouvoir décider en cinq secondes s'il doit agir.

L'objet d'un courriel est l'élément le plus important et le plus négligé. « Point » ou « Question » n'informe personne. « Validation du budget formation avant vendredi 12 » indique le sujet, l'action et l'échéance. Un bon objet permet aussi de retrouver le message des mois plus tard.

La structure recommandée est la pyramide inversée, héritée du journalisme : l'essentiel d'abord, les détails ensuite. Le lecteur pressé s'arrête après le premier paragraphe et dispose déjà de l'information utile. L'ordre inverse, qui garde la conclusion pour la fin, oblige à tout lire.

La concision se travaille à la relecture. Les formules de politesse excessives, les répétitions et les précautions oratoires allongent le texte sans rien ajouter. Une phrase de plus de trente mots gagne presque toujours à être coupée en deux.

Le ton s'adapte au destinataire sans jamais devenir familier dans un cadre professionnel. Le tutoiement suit l'usage de l'organisation. L'humour et l'ironie passent mal à l'écrit, car le lecteur ne dispose ni du ton de voix ni des expressions du visage pour les interpréter.

Trois règles pratiques évitent la plupart des incidents. Ne jamais écrire un message important sous le coup de l'émotion ; le rédiger, puis le relire une heure plus tard. Vérifier les destinataires avant l'envoi, en particulier avant un « répondre à tous ». Et considérer qu'un message professionnel peut toujours être transféré à quelqu'un d'autre : n'y écrire que ce que l'on assumerait devant un tiers.""",
    },
    {
        "title": "Réussir une présentation orale et sa soutenance",
        "category": "Communication",
        "level": "Intermédiaire",
        "keywords": "présentation, oral, soutenance, diaporama, slides, trac, questions, jury, argumentation",
        "summary": "Préparer, structurer et livrer une présentation convaincante devant un jury.",
        "content": """Une présentation se prépare en partant de l'auditoire, pas du contenu. Ce que le jury connaît déjà, ce qu'il cherche à évaluer et le temps dont il dispose déterminent ce qui doit être dit et ce qui peut être omis.

La structure la plus solide tient en trois temps. L'introduction pose le contexte, le problème et annonce le plan. Le développement traite trois à quatre idées principales, pas davantage : au-delà, l'auditoire ne retient plus rien. La conclusion rappelle le message essentiel et ouvre sur les perspectives.

Le diaporama soutient le discours, il ne le remplace pas. Une diapositive chargée de texte contraint l'auditoire à choisir entre lire et écouter, et il fait généralement mal ce choix. Une idée par diapositive, des mots-clés plutôt que des phrases, et un graphique lisible depuis le fond de la salle valent mieux qu'un support exhaustif. Le détail appartient au rapport écrit.

La répétition à voix haute est ce qui distingue une présentation maîtrisée d'une présentation improvisée. Elle révèle les enchaînements bancals et permet de caler le minutage. Dépasser son temps est l'une des fautes les plus pénalisées, car cela empiète sur les questions.

Le trac est physiologique et ne disparaît pas ; il se canalise. Une respiration lente avant de commencer, un débit volontairement ralenti sur les premières phrases et un regard qui circule dans la salle suffisent à le rendre invisible. Les silences ne sont pas des vides : ils ponctuent et donnent du poids.

La séance de questions se prépare autant que l'exposé. Anticiper cinq questions probables, en particulier sur les limites du travail, évite d'être déstabilisé. Reconnaître honnêtement une limite est perçu comme de la rigueur ; tenter de la masquer est perçu comme un manque de recul. Quand une question n'est pas comprise, il vaut mieux demander une reformulation que répondre à côté.""",
    },
]


# ===========================================================================
#  Quiz de démonstration
# ===========================================================================

QUIZZES: list[dict] = [
    {
        "title": "Python — les bases",
        "category": "Python",
        "difficulty": "Facile",
        "passing_score": 60,
        "description": "Variables, types, boucles et fonctions. Basé sur les fiches Python de la bibliothèque.",
        "questions": [
            {
                "question_text": "Que renvoie l'expression type(3.14) en Python ?",
                "options": ["int", "float", "str", "decimal"],
                "correct_index": 1,
                "explanation": "Un nombre écrit avec un point décimal est de type float.",
            },
            {
                "question_text": "Quelle suite de nombres la fonction range(1, 6) génère-t-elle ?",
                "options": ["1, 2, 3, 4, 5, 6", "1, 2, 3, 4, 5", "0, 1, 2, 3, 4, 5", "1 à 6 avec un pas de 2"],
                "correct_index": 1,
                "explanation": "La borne finale de range() est toujours exclue : range(1, 6) s'arrête à 5.",
            },
            {
                "question_text": "Quelle est la différence entre print et return dans une fonction ?",
                "options": [
                    "Aucune, ce sont deux synonymes",
                    "print affiche à l'écran, return renvoie une valeur exploitable par l'appelant",
                    "return affiche à l'écran, print renvoie une valeur",
                    "print est réservé aux chaînes de caractères",
                ],
                "correct_index": 1,
                "explanation": "print produit un affichage mais ne rend rien ; return fournit une valeur que l'appelant peut stocker.",
            },
            {
                "question_text": "Comment accéder de façon sûre à une clé qui peut être absente d'un dictionnaire ?",
                "options": [
                    "dictionnaire[cle]",
                    "dictionnaire.get(cle)",
                    "dictionnaire.find(cle)",
                    "dictionnaire.index(cle)",
                ],
                "correct_index": 1,
                "explanation": "get() renvoie None (ou une valeur par défaut) au lieu de lever une KeyError.",
            },
            {
                "question_text": "Que fait l'instruction break à l'intérieur d'une boucle ?",
                "options": [
                    "Elle saute le tour courant et passe au suivant",
                    "Elle interrompt la boucle et passe à la suite du programme",
                    "Elle relance la boucle depuis le début",
                    "Elle met la boucle en pause",
                ],
                "correct_index": 1,
                "explanation": "break sort de la boucle ; c'est continue qui saute uniquement le tour courant.",
            },
        ],
    },
    {
        "title": "Data — clustering et classification",
        "category": "Data",
        "difficulty": "Moyen",
        "passing_score": 60,
        "description": "K-Means, arbres de décision et évaluation des modèles.",
        "questions": [
            {
                "question_text": "K-Means est un algorithme d'apprentissage :",
                "options": ["supervisé", "non supervisé", "par renforcement", "semi-supervisé uniquement"],
                "correct_index": 1,
                "explanation": "K-Means regroupe les individus sans utiliser d'étiquettes connues à l'avance.",
            },
            {
                "question_text": "Pourquoi normaliser les données avant d'appliquer K-Means ?",
                "options": [
                    "Pour accélérer le calcul",
                    "Parce que l'algorithme raisonne en distances : sans normalisation, une variable à grande échelle écrase les autres",
                    "Parce que scikit-learn refuse les valeurs négatives",
                    "Ce n'est pas nécessaire pour K-Means",
                ],
                "correct_index": 1,
                "explanation": "Une variable de 0 à 40 dominerait complètement une variable de 1 à 5 dans le calcul des distances.",
            },
            {
                "question_text": "À quoi sert la méthode du coude (elbow) ?",
                "options": [
                    "À mesurer l'exactitude du modèle",
                    "À choisir le nombre de clusters k",
                    "À supprimer les valeurs aberrantes",
                    "À équilibrer les classes",
                ],
                "correct_index": 1,
                "explanation": "On trace l'inertie en fonction de k et l'on retient la valeur où la courbe se casse.",
            },
            {
                "question_text": "Un modèle atteint 100 % sur les données d'entraînement et 55 % sur les données de test. De quoi s'agit-il ?",
                "options": [
                    "D'un excellent modèle",
                    "De surapprentissage : le modèle a mémorisé au lieu d'apprendre la règle",
                    "D'un sous-apprentissage",
                    "D'une erreur de normalisation",
                ],
                "correct_index": 1,
                "explanation": "L'écart important entre entraînement et test est la signature du surapprentissage.",
            },
            {
                "question_text": "Pour repérer des apprenants en décrochage, quel indicateur faut-il privilégier ?",
                "options": [
                    "La précision, pour éviter les fausses alertes",
                    "Le rappel, pour ne laisser passer aucun cas réel",
                    "L'exactitude seule",
                    "Aucun, tous sont équivalents",
                ],
                "correct_index": 1,
                "explanation": "Mieux vaut alerter à tort que laisser un apprenant décrocher sans réaction : le rappel prime.",
            },
            {
                "question_text": "Que montre la diagonale d'une matrice de confusion ?",
                "options": [
                    "Les erreurs du modèle",
                    "Les prédictions correctes",
                    "Le nombre total d'exemples",
                    "L'importance des variables",
                ],
                "correct_index": 1,
                "explanation": "La diagonale croise catégorie réelle et catégorie prédite identiques : ce sont les bonnes réponses.",
            },
        ],
    },
    {
        "title": "Web — HTML, CSS, React et API REST",
        "category": "Web",
        "difficulty": "Moyen",
        "passing_score": 60,
        "description": "Structure d'une page, composants React et conception d'API.",
        "questions": [
            {
                "question_text": "Quel code de statut HTTP correspond à « authentifié mais sans les droits nécessaires » ?",
                "options": ["401", "403", "404", "422"],
                "correct_index": 1,
                "explanation": "401 signifie « je ne sais pas qui vous êtes », 403 « je sais qui vous êtes et c'est refusé ».",
            },
            {
                "question_text": "En React, que se passe-t-il si l'on modifie directement une variable d'état au lieu d'utiliser sa fonction setter ?",
                "options": [
                    "L'interface se met à jour normalement",
                    "Aucun nouveau rendu n'est déclenché : l'affichage ne change pas",
                    "React lève une exception bloquante",
                    "Le composant est démonté",
                ],
                "correct_index": 1,
                "explanation": "Seul l'appel du setter informe React qu'un nouveau rendu est nécessaire.",
            },
            {
                "question_text": "Quelle règle CSS inclut le padding et la bordure dans la largeur déclarée d'un élément ?",
                "options": [
                    "display: flex",
                    "box-sizing: border-box",
                    "position: relative",
                    "overflow: hidden",
                ],
                "correct_index": 1,
                "explanation": "Sans border-box, la largeur ne concerne que le contenu, ce qui complique tous les calculs.",
            },
            {
                "question_text": "Quelle URL respecte les conventions REST pour lister les apprenants ?",
                "options": [
                    "GET /api/getApprenants",
                    "GET /api/apprenants",
                    "POST /api/apprenants/liste",
                    "GET /api/apprenant?action=list",
                ],
                "correct_index": 1,
                "explanation": "L'action est portée par le verbe HTTP ; l'URL ne désigne que la ressource.",
            },
            {
                "question_text": "Pourquoi masquer un bouton dans l'interface ne suffit-il pas à sécuriser une action ?",
                "options": [
                    "Parce que le bouton peut réapparaître après rechargement",
                    "Parce que l'API peut être appelée directement, sans passer par l'interface",
                    "Parce que CSS n'est pas fiable",
                    "Ce n'est pas vrai, c'est suffisant",
                ],
                "correct_index": 1,
                "explanation": "Tout contrôle de droits doit être appliqué côté serveur ; l'interface n'est qu'un confort.",
            },
        ],
    },
    {
        "title": "Management — gestion de projet et animation d'équipe",
        "category": "Management",
        "difficulty": "Facile",
        "passing_score": 60,
        "description": "Cycle en V, Scrum, conduite de réunion et délégation.",
        "questions": [
            {
                "question_text": "Dans Scrum, qui priorise le backlog ?",
                "options": ["Le Scrum Master", "Le Product Owner", "L'équipe de développement", "Le client final"],
                "correct_index": 1,
                "explanation": "Le Product Owner porte la vision produit et ordonne le backlog.",
            },
            {
                "question_text": "Quelle est la principale faiblesse du cycle en V ?",
                "options": [
                    "Il est trop coûteux à documenter",
                    "Sa rigidité : le client ne voit un résultat qu'à la fin et tout changement coûte cher",
                    "Il ne permet pas les tests",
                    "Il exige une équipe de plus de dix personnes",
                ],
                "correct_index": 1,
                "explanation": "Chaque changement remet en cause des phases déjà validées.",
            },
            {
                "question_text": "Qu'est-ce qui distingue une action d'une simple intention en fin de réunion ?",
                "options": [
                    "Sa présence au compte rendu",
                    "Un responsable nommé et une échéance",
                    "Son urgence",
                    "L'accord de tous les participants",
                ],
                "correct_index": 1,
                "explanation": "Sans propriétaire ni date, une action n'est qu'une intention.",
            },
            {
                "question_text": "Déléguer correctement, c'est :",
                "options": [
                    "Distribuer des tâches en précisant chaque étape",
                    "Transférer une responsabilité avec la marge de manœuvre correspondante",
                    "Confier le travail au plus expérimenté",
                    "Partager la charge à parts égales",
                ],
                "correct_index": 1,
                "explanation": "Imposer chaque étape n'est pas de la délégation mais de l'exécution supervisée.",
            },
        ],
    },
    {
        "title": "Communication — écrit professionnel et oral",
        "category": "Communication",
        "difficulty": "Facile",
        "passing_score": 60,
        "description": "Rédaction de messages clairs et préparation d'une soutenance.",
        "questions": [
            {
                "question_text": "Qu'est-ce que la structure en pyramide inversée ?",
                "options": [
                    "Commencer par le contexte et finir par la conclusion",
                    "Donner l'essentiel dès le début, les détails ensuite",
                    "Alterner arguments et contre-arguments",
                    "Numéroter chaque paragraphe",
                ],
                "correct_index": 1,
                "explanation": "Le lecteur pressé s'arrête après le premier paragraphe et dispose déjà de l'information utile.",
            },
            {
                "question_text": "Quel objet de courriel est le plus efficace ?",
                "options": [
                    "Question",
                    "Validation du budget formation avant vendredi 12",
                    "Urgent !!!",
                    "Suite à notre échange",
                ],
                "correct_index": 1,
                "explanation": "Un bon objet indique le sujet, l'action attendue et l'échéance.",
            },
            {
                "question_text": "Combien d'idées principales une présentation orale doit-elle comporter au maximum ?",
                "options": ["Une seule", "Trois à quatre", "Sept à huit", "Autant que le temps le permet"],
                "correct_index": 1,
                "explanation": "Au-delà de trois ou quatre idées, l'auditoire ne retient plus rien.",
            },
            {
                "question_text": "Face à une question du jury portant sur une limite de votre travail, la meilleure attitude est :",
                "options": [
                    "Minimiser la limite pour protéger le travail",
                    "Reconnaître la limite honnêtement et expliquer ce qu'elle implique",
                    "Renvoyer la question au rapport écrit",
                    "Changer de sujet",
                ],
                "correct_index": 1,
                "explanation": "Reconnaître une limite est perçu comme de la rigueur ; la masquer trahit un manque de recul.",
            },
        ],
    },
]


# ===========================================================================


def _author(db) -> User | None:
    """Formateur ou administrateur à qui attribuer les contenus créés."""
    return db.execute(
        select(User)
        .where(User.role.in_([ROLE_TRAINER, ROLE_ADMIN]))
        .order_by(User.role.desc(), User.id)
        .limit(1)
    ).scalar_one_or_none()


def seed_courses(db, author_id: int | None) -> int:
    existing = {
        title for title in db.execute(select(CourseResource.title)).scalars()
    }
    created = 0
    for course in COURSES:
        if course["title"] in existing:
            continue
        db.add(
            CourseResource(
                title=course["title"],
                category=course["category"],
                level=course["level"],
                summary=course["summary"],
                keywords=course["keywords"],
                content=course["content"].strip(),
                created_by_id=author_id,
            )
        )
        created += 1
    db.commit()
    knowledge_service.invalidate()
    return created


def seed_quizzes(db, author_id: int | None) -> int:
    existing = {title for title in db.execute(select(Quiz.title)).scalars()}
    created = 0
    for spec in QUIZZES:
        if spec["title"] in existing:
            continue
        quiz = Quiz(
            title=spec["title"],
            description=spec["description"],
            category=spec["category"],
            difficulty=spec["difficulty"],
            passing_score=spec["passing_score"],
            is_published=True,
            created_by_id=author_id,
        )
        db.add(quiz)
        db.flush()
        for position, question in enumerate(spec["questions"]):
            db.add(
                QuizQuestion(
                    quiz_id=quiz.id,
                    position=position,
                    question_text=question["question_text"],
                    options=question["options"],
                    correct_index=question["correct_index"],
                    points=1.0,
                    explanation=question.get("explanation"),
                )
            )
        created += 1
    db.commit()
    return created


def assign_demo_quizzes(db, author_id: int | None) -> int:
    """Attribue à chaque apprenant disposant d'un compte les quiz de sa filière."""
    learners = list(
        db.execute(select(Learner).where(Learner.user_id.is_not(None)).order_by(Learner.id)).scalars()
    )
    if not learners:
        return 0

    quizzes = list(db.execute(select(Quiz).where(Quiz.is_published.is_(True))).scalars())
    total = 0
    for learner in learners:
        # Quiz de la filière de l'apprenant, plus un quiz transverse.
        targeted = [q for q in quizzes if q.category == learner.course_category]
        transverse = [q for q in quizzes if q.category == "Communication"]
        for quiz in {q.id: q for q in targeted + transverse[:1]}.values():
            result = quiz_service.assign_quiz(db, quiz, [learner.id], author_id)
            total += result["assigned"]
    return total


def run(reset: bool = False) -> int:
    if not settings.database_configured:
        print("ERREUR : DATABASE_URL n'est pas définie (voir backend/.env.example).")
        return 2

    ok, message = check_connection()
    print(f"Connexion : {message}")
    if not ok:
        return 3

    create_all()

    with session_scope() as db:
        if reset:
            titles = [c["title"] for c in COURSES]
            deleted_courses = 0
            for resource in db.execute(
                select(CourseResource).where(CourseResource.title.in_(titles))
            ).scalars():
                db.delete(resource)
                deleted_courses += 1
            quiz_titles = [q["title"] for q in QUIZZES]
            deleted_quizzes = 0
            for quiz in db.execute(select(Quiz).where(Quiz.title.in_(quiz_titles))).scalars():
                db.delete(quiz)
                deleted_quizzes += 1
            db.commit()
            knowledge_service.invalidate()
            print(f"Réinitialisation : {deleted_courses} fiche(s) et {deleted_quizzes} quiz supprimés")

        author = _author(db)
        author_id = author.id if author else None
        if author is None:
            print("  ! Aucun formateur ni administrateur trouvé : les contenus n'auront pas d'auteur.")

        courses_created = seed_courses(db, author_id)
        total_courses = db.execute(select(func.count(CourseResource.id))).scalar_one()
        print(f"Bibliothèque : {courses_created} fiche(s) ajoutée(s) — {total_courses} au total")

        quizzes_created = seed_quizzes(db, author_id)
        total_quizzes = db.execute(select(func.count(Quiz.id))).scalar_one()
        print(f"Quiz         : {quizzes_created} créé(s) — {total_quizzes} au total")

        assigned = assign_demo_quizzes(db, author_id)
        print(f"Attributions : {assigned} nouvelle(s) attribution(s) aux apprenants avec compte")

    print("\nContenus prêts. L'AI Tutor peut désormais répondre aux questions de cours.")
    return 0


def main_with_defaults() -> int:
    return run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bibliothèque de cours et quiz de démonstration")
    parser.add_argument("--reset", action="store_true", help="Supprimer puis recréer les contenus de démonstration")
    parsed = parser.parse_args()
    return run(reset=parsed.reset)


if __name__ == "__main__":
    sys.exit(main())
