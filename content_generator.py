"""
content_generator.py
Génère et édite des posts LinkedIn via Claude API ou Perplexity API.

Distribution des types de posts :
  75% → Posts de fond (éducatif, conseil, réflexion, tendance, opinion)
  15% → Posts personnels ("j'ai fait", expérience concrète)
  10% → Posts actualité (réaction à une news, réforme, tendance du moment)

Le provider est sélectionné aléatoirement à chaque appel selon les poids
définis dans config.py (PROVIDER_WEIGHTS). Par défaut 30% Claude / 70% Perplexity.

Les system prompts sont lus dynamiquement depuis :
  prompts/theme_finance_compta.md
  prompts/theme_tech_ia.md
→ Modifie ces fichiers sans redémarrer le bot.
"""

import random
import logging
from pathlib import Path
from typing import Optional, Tuple

from anthropic import Anthropic
from openai import OpenAI

from config import (
    ANTHROPIC_API_KEY,
    PERPLEXITY_API_KEY,
    CLAUDE_MODEL,
    PERPLEXITY_MODEL,
    PROVIDER_WEIGHTS,
)

logger = logging.getLogger(__name__)

# ─── Clients API ──────────────────────────────────────────────────────────────
claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)

perplexity_client = OpenAI(
    api_key=PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai",
)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ─── Thèmes → fichiers prompts ────────────────────────────────────────────────
THEMES = {
    "Finance, Compta & Gestion": PROMPTS_DIR / "theme_finance_compta.md",
    "Tech & IA appliquée à la Finance": PROMPTS_DIR / "theme_tech_ia.md",
}

# ─── Sujets forcés par thème (rotation obligatoire) ──────────────────────────
# Le sujet est tiré au sort et injecté dans le prompt pour éviter la répétition
FORCED_TOPICS = {
    "Finance, Compta & Gestion": [
        "Facturation électronique : les entreprises qui ne se préparent pas maintenant vont souffrir",
        "Clôture mensuelle : pourquoi attendre le 15 du mois suivant est un luxe qu'on ne peut plus se permettre",
        "Le budget annuel est mort. Vive le rolling forecast",
        "DSO, DPO, DIO : les 3 ratios que tout DAF devrait connaître par cœur",
        "Audit interne PME : pas besoin d'une équipe dédiée pour bien contrôler",
        "La différence entre un expert-comptable et un vrai partenaire financier",
        "Pourquoi votre résultat comptable ne reflète pas la santé réelle de votre entreprise",
        "SIG : le compte de résultat ne suffit pas pour piloter",
        "Cash is king : 5 leviers concrets pour améliorer sa trésorerie sans lever de fonds",
        "La paie externalisée : avantages, risques, et ce qu'on ne te dit pas",
        "Holding vs société opérationnelle : quand ça vaut le coup de structurer",
        "Pourquoi les PME sous-estiment toujours leur besoin en fonds de roulement",
        "Rapport de gestion mensuel : les 5 indicateurs qui comptent vraiment",
        "TVA intracommunautaire : les erreurs qui coûtent cher",
        "Passer de la comptabilité de trésorerie à la comptabilité d'engagement",
        "La cession d'entreprise : ce que les chiffres ne montrent pas",
        "Contrôle de gestion sans ERP : c'est possible, voilà comment",
        "Filiale étrangère en France : les pièges comptables et fiscaux à éviter",
        "Marges par produit/client : pourquoi 80% des PME pilotent à l'aveugle",
        "Plan de financement vs plan de trésorerie : la confusion qui coûte cher",
        "Les provisions : souvent oubliées, toujours importantes",
        "Tableaux de bord financiers : moins d'indicateurs, plus d'impact",
        "Optimisation fiscale légale : ce que les dirigeants de PME ignorent souvent",
        "La vraie valeur d'un DAF à temps partagé pour une PME",
        "Post-levée de fonds : comment structurer son pilotage financier rapidement",
    ],
    "Tech & IA appliquée à la Finance": [
        "Power Query vs VBA : arrêtez de coder ce que Power Query fait en 3 clics",
        "Un dashboard Power BI pour les nuls en finance : par où commencer vraiment",
        "Python pour les contrôleurs de gestion : cas d'usage concrets et accessibles",
        "ChatGPT dans Excel : ce que ça change pour les équipes finance au quotidien",
        "Les 5 automatisations Excel que toute équipe finance devrait avoir",
        "SQL pour analyser ses données comptables sans passer par l'IT",
        "Connecter son ERP à Power BI : les erreurs classiques et comment les éviter",
        "IA générative et clôture comptable : ce qui est déjà possible aujourd'hui",
        "Réconciliation bancaire automatique : techniquement simple, souvent ignorée",
        "Make vs Zapier pour automatiser les process financiers : comparatif honnête",
        "Agents IA en finance : au-delà du buzz, ce qui fonctionne vraiment",
        "Le reporting qui prenait 3 jours se fait maintenant en 30 minutes",
        "Extraction automatique de données depuis des PDF de factures",
        "Prévisionnels de trésorerie en temps réel : architecture simple avec Python",
        "Traitement des notes de frais : 0 intervention humaine, c'est possible",
        "Consolidation multi-entités automatisée sans ERP de groupe",
        "OCR et comptabilité : comment automatiser la saisie des factures fournisseurs",
        "Data warehouse financier léger : pourquoi une PME en a besoin",
        "Dématérialisation des archives comptables : contraintes légales et solutions pratiques",
        "Tableau vs Power BI vs Looker : lequel choisir pour une équipe finance",
        "Les limites de l'IA en finance : ce qu'elle ne fera jamais à ta place",
        "Automatiser ses relances clients avec un script Python simple",
        "API open banking : comment récupérer ses données bancaires automatiquement",
        "Low-code et finance : les outils qui changent vraiment la vie des équipes",
        "Intégration Pennylane / Sellsy / Qonto → Power BI : retour d'expérience",
    ],
}

# ─── Distribution des types de posts ─────────────────────────────────────────
POST_TYPE_WEIGHTS = {
    "general": 0.75,    # Post éducatif, conseil, réflexion, tendance, opinion
    "personal": 0.15,   # Post "j'ai fait", expérience personnelle concrète
    "news": 0.10,       # Post actualité, réaction à une news ou réforme
}

POST_TYPE_INSTRUCTIONS = {
    "general": (
        "TYPE DE POST : Post de fond (75% des posts).\n"
        "Génère un post éducatif, de réflexion, de conseil pratique, de tendance, mythe vs réalité ou prise de position.\n"
        "Parle en expert qui partage une connaissance ou un point de vue - pas une expérience personnelle récente.\n"
        "Reste dans la perspective 'on', 'les équipes', 'les entreprises', 'les dirigeants' - pas 'j'ai fait'.\n"
        "Angles prioritaires : éducatif, question/réflexion, conseil pratique, mythe vs réalité, opinion tranchée.\n"
        "CLÔTURE OBLIGATOIRE : une question ouverte factuelle. Objectif portée/engagement, pas conversion directe.\n"
        "Jamais de CTA message privé sur ce type de post."
    ),
    "personal": (
        "TYPE DE POST : Post personnel / expérience (15% des posts).\n"
        "Génère un post à la première personne dès la première ligne, ancré dans une expérience ou réalisation concrète.\n"
        "Ici, commencer par 'Je' est attendu - c'est l'exception à la règle générale d'ouverture du prompt système.\n"
        "Angles possibles : avant/après, leçon apprise, outil que j'ai construit, process que j'ai optimisé.\n"
        "Ton factuel, sans sur-vente. Montre la valeur par le concret et les chiffres.\n"
        "Évite les formulations trop commerciales ou auto-congratulatoires.\n"
        "CLÔTURE OBLIGATOIRE : un appel à l'action court vers le message privé. Objectif conversion directe.\n"
        "Jamais de question en plus du CTA."
    ),
    "news": (
        "TYPE DE POST : Post actualité (10% des posts).\n"
        "Génère un post qui réagit à une actualité récente ou tendance du moment en finance, data, IA ou tech.\n"
        "Prends une position claire et argumentée. Ton : expert, réactif, pertinent.\n"
        "Structure : accroche sur l'actualité → analyse → implication concrète → clôture.\n"
        "Exemples d'angles : réforme réglementaire, nouveau modèle d'IA, évolution des pratiques de gestion.\n"
        "CLÔTURE OBLIGATOIRE : une question ouverte qui invite un vrai avis en commentaire. Pas de CTA message privé."
    ),
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_prompt(theme: str) -> str:
    """
    Charge le system prompt depuis le .md du thème. Relu à chaque appel.
    Si un fichier .local.md existe (version personnalisée, non versionnée),
    il est utilisé en priorité - ex: theme_finance_compta.local.md
    """
    prompt_file = THEMES.get(theme)
    if not prompt_file:
        raise FileNotFoundError(f"Thème inconnu : '{theme}'")

    local_file = prompt_file.with_name(prompt_file.stem + ".local.md")
    if local_file.exists():
        return local_file.read_text(encoding="utf-8").strip()

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Fichier prompt introuvable pour '{theme}' → {prompt_file}"
        )
    return prompt_file.read_text(encoding="utf-8").strip()


def pick_theme() -> str:
    """Tire un thème au hasard."""
    return random.choice(list(THEMES.keys()))


def pick_post_type() -> str:
    """
    Sélectionne un type de post selon les poids définis dans POST_TYPE_WEIGHTS.
    75% général / 15% personnel / 10% actualité.
    """
    types = list(POST_TYPE_WEIGHTS.keys())
    weights = list(POST_TYPE_WEIGHTS.values())
    return random.choices(types, weights=weights, k=1)[0]


def pick_provider() -> str:
    """
    Sélectionne un provider selon les poids définis dans PROVIDER_WEIGHTS.
    Ex: {"claude": 0.30, "perplexity": 0.70} → 70% de chance de Perplexity.
    """
    providers = list(PROVIDER_WEIGHTS.keys())
    weights = list(PROVIDER_WEIGHTS.values())
    return random.choices(providers, weights=weights, k=1)[0]


# ─── Appels API ───────────────────────────────────────────────────────────────

def _call_claude(system_prompt: str, user_message: str) -> str:
    """Appel Claude API (Anthropic)."""
    response = claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def _call_perplexity(system_prompt: str, user_message: str) -> str:
    """Appel Perplexity API (compatible OpenAI)."""
    response = perplexity_client.chat.completions.create(
        model=PERPLEXITY_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_llm(system_prompt: str, user_message: str, force_provider: Optional[str] = None) -> Tuple[str, str]:
    """
    Appelle le bon provider selon le tirage aléatoire (ou force_provider).
    Retourne (texte_généré, provider_utilisé).
    En cas d'erreur sur un provider, bascule automatiquement sur l'autre.
    """
    provider = force_provider or pick_provider()

    try:
        if provider == "claude":
            result = _call_claude(system_prompt, user_message)
        else:
            result = _call_perplexity(system_prompt, user_message)
        logger.info(f"Provider utilisé : {provider.upper()}")
        return result, provider

    except Exception as e:
        fallback = "perplexity" if provider == "claude" else "claude"
        logger.warning(f"Erreur {provider} ({e}) → bascule sur {fallback}")
        try:
            if fallback == "claude":
                result = _call_claude(system_prompt, user_message)
            else:
                result = _call_perplexity(system_prompt, user_message)
            logger.info(f"Fallback réussi sur : {fallback.upper()}")
            return result, fallback
        except Exception as e2:
            raise RuntimeError(
                f"Les deux providers ont échoué.\nClaude: {e}\nPerplexity: {e2}"
            )


# ─── Génération d'un post ─────────────────────────────────────────────────────

def generate_post(theme: Optional[str] = None, custom_brief: Optional[str] = None, post_type: Optional[str] = None) -> Tuple[str, str]:
    """
    Génère un post LinkedIn.

    Args:
        theme: clé du thème (tiré au sort si None)
        custom_brief: sujet libre fourni via /brief
        post_type: 'general', 'personal' ou 'news' (tiré au sort si None)

    Returns:
        (contenu du post, thème utilisé)
    """
    if not theme:
        theme = pick_theme()

    if not post_type:
        post_type = pick_post_type()

    system_prompt = load_prompt(theme)
    type_instruction = POST_TYPE_INSTRUCTIONS[post_type]

    if custom_brief:
        forced_subject = custom_brief
    else:
        # Sujet forcé tiré au sort pour garantir la variété
        topics = FORCED_TOPICS.get(theme, list(FORCED_TOPICS.values())[0])
        forced_subject = random.choice(topics)

    user_message = (
        f"{type_instruction}\n\n"
        f"SUJET OBLIGATOIRE : {forced_subject}\n\n"
        "Traite EXACTEMENT ce sujet - n'en change pas.\n"
        "Trouve un angle original et une accroche forte.\n"
        "Reste concret, direct, évite les généralités."
    )

    logger.info(f"Génération | thème : {theme} | type : {post_type}")
    post, provider = _call_llm(system_prompt, user_message)
    logger.info(f"Post généré ({len(post.split())} mots) via {provider.upper()}")
    return post, theme


# ─── Édition ciblée ───────────────────────────────────────────────────────────

def edit_post(original_post: str, instruction: str, theme: Optional[str] = None) -> str:
    """
    Applique une modification ciblée sur un post existant.
    Garde 95%+ du texte intact, change uniquement ce qui est demandé.

    Args:
        original_post: texte du post à modifier
        instruction: ex: "remplace 15 par 13", "reformule la conclusion"
        theme: thème du post (optionnel)

    Returns:
        Post avec la modification appliquée
    """
    system = (
        "Tu es un assistant d'édition de posts LinkedIn.\n"
        "Ta mission : appliquer UNE modification précise sur un post existant.\n\n"
        "RÈGLES STRICTES :\n"
        "- Garde le texte d'origine à 95%+ intact\n"
        "- Change UNIQUEMENT ce que l'instruction demande\n"
        "- Ne reformule pas, ne réécris pas, n'améliores pas le reste\n"
        "- Conserve la structure, les hashtags, le ton\n"
        "- Retourne UNIQUEMENT le post modifié, sans commentaire"
    )

    user_message = (
        f"Post original :\n\n{original_post}\n\n"
        f"---\n\n"
        f"Instruction : {instruction}\n\n"
        f"Retourne le post avec uniquement cette modification appliquée."
    )

    logger.info(f"Édition ciblée | instruction : {instruction[:80]}...")
    result, provider = _call_llm(system, user_message, force_provider="claude")
    return result


# ─── Nouveau post from scratch ────────────────────────────────────────────────

def new_post(previous_post: Optional[str] = None, theme: Optional[str] = None) -> Tuple[str, str]:
    """
    Génère un post entièrement nouveau, angle différent du précédent.

    Args:
        previous_post: post précédent (pour éviter de répéter)
        theme: forcer un thème spécifique (sinon tiré au sort)

    Returns:
        (contenu du nouveau post, thème utilisé)
    """
    if not theme:
        theme = pick_theme()

    post_type = pick_post_type()
    system_prompt = load_prompt(theme)
    type_instruction = POST_TYPE_INSTRUCTIONS[post_type]

    if previous_post:
        user_message = (
            f"{type_instruction}\n\n"
            "Génère un post COMPLÈTEMENT DIFFÉRENT du précédent.\n\n"
            f"Post précédent à ne pas reproduire :\n{previous_post[:400]}...\n\n"
            "Change l'angle, le sujet, le style. Ne reprends aucune formulation."
        )
    else:
        user_message = (
            f"{type_instruction}\n\n"
            "Génère un post original sur ce thème.\n"
            "Trouve un angle frais et une accroche qui sort du lot."
        )

    logger.info(f"Nouveau post | thème : {theme} | type : {post_type}")
    post, provider = _call_llm(system_prompt, user_message)
    logger.info(f"Nouveau post généré ({len(post.split())} mots) via {provider.upper()}")
    return post, theme
