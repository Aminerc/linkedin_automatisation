"""
content_generator.py
Génère et édite des posts LinkedIn via Claude API ou Perplexity API.

Distribution des types de posts :
  75% → Posts de fond (éducatif, conseil, réflexion, tendance, opinion)
  15% → Posts personnels ("j'ai fait", expérience concrète)
  10% → Posts actualité (réaction à une news, réforme, tendance du moment)

Le provider est sélectionné aléatoirement à chaque appel selon les poids
définis dans config.py (PROVIDER_WEIGHTS). Par défaut 30% Claude / 70% Perplexity.

Thème unique "Pilotage de PME" : le system prompt est lu dynamiquement depuis
  prompts/theme_pme.local.md (prioritaire, non versionné) ou prompts/theme_pme.md
→ Modifie ces fichiers sans redémarrer le bot.
Variété : un domaine (argent, clients, équipe, opérations, outils, dirigeant)
puis un sujet sont tirés au sort en évitant les derniers utilisés.
"""

import json
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

THEME_NAME = "Pilotage de PME"

# ─── Thème unique → fichier prompt ────────────────────────────────────────────
THEMES = {
    THEME_NAME: PROMPTS_DIR / "theme_pme.md",
}

# Anciens noms de thèmes (posts en attente, callbacks Telegram) → thème unique
LEGACY_THEMES = {
    "Finance, Compta & Gestion": THEME_NAME,
    "Tech & IA appliquée à la Finance": THEME_NAME,
}

# ─── Domaines et sujets (rotation anti-répétition) ────────────────────────────
# Tout ce qui fait la vie d'une PME. Le domaine et le sujet sont tirés au sort
# en évitant les derniers utilisés (historique dans data/topics_history.json).
DOMAINS = {
    "argent": "Trésorerie, marges et rentabilité",
    "clients": "Clients, ventes et prix",
    "equipe": "Équipe, recrutement et organisation",
    "operations": "Achats, stocks et production",
    "outils": "Outils, automatisation et temps gagné",
    "dirigeant": "Décisions et quotidien du dirigeant",
}

FORCED_TOPICS = {
    "argent": [
        "Le chiffre d'affaires monte et le compte en banque ne suit pas",
        "Les clients qui paient à 60 jours pendant que vous payez vos fournisseurs à 30",
        "Savoir combien il restera sur le compte dans 8 semaines, pas seulement aujourd'hui",
        "Le résultat comptable de l'an dernier ne dit rien de la marge de ce mois-ci",
        "Les produits ou services qui font du volume mais ne rapportent rien",
        "Le prix de revient que personne n'a recalculé depuis 3 ans",
        "Les frais fixes qui ont grossi sans que personne ne décide",
        "Ce qu'une facture envoyée 10 jours trop tard coûte en trésorerie",
        "Le seuil de rentabilité : à partir de quel chiffre le mois commence à rapporter",
        "Préparer un rendez-vous avec son banquier avec des chiffres qu'il comprend",
        "Les abonnements et contrats qui tournent encore et ne servent plus",
        "La facturation électronique obligatoire : ce que ça change concrètement au quotidien",
    ],
    "clients": [
        "Le client qui fait 30 % du chiffre d'affaires : force ou danger",
        "Augmenter ses prix sans perdre ses clients : regarder d'abord la marge par client",
        "Les devis envoyés qui ne sont jamais relancés",
        "Les remises accordées au cas par cas qui mangent la marge",
        "Savoir quels clients ne sont pas revenus depuis 6 mois",
        "Relancer un impayé sans abîmer la relation client",
        "Le commercial qui vend beaucoup mais à faible marge",
        "Suivre ses prospects dans un carnet, un Excel ou la tête du dirigeant",
        "Le coût réel d'un client difficile : temps passé, litiges, retards",
        "Pourquoi le meilleur mois en chiffre d'affaires n'est pas toujours le meilleur mois en marge",
        "Les petits clients qui coûtent plus qu'ils ne rapportent",
        "Fidéliser coûte moins cher que prospecter : le calcul sur vos propres chiffres",
    ],
    "equipe": [
        "Quand une seule personne connaît le fichier qui fait tourner l'entreprise",
        "Le vrai coût d'un recrutement raté dans une petite structure",
        "La masse salariale qui augmente plus vite que le chiffre d'affaires",
        "Les heures passées à recopier des chiffres d'un fichier à l'autre",
        "L'absentéisme et le turnover : ce qu'ils coûtent vraiment",
        "Déléguer sans perdre la visibilité sur ce qui se passe",
        "Les réunions du lundi où chacun arrive avec un chiffre différent",
        "Préparer l'arrivée d'un nouveau salarié sans que tout repose sur le dirigeant",
        "Le temps passé par l'équipe sur des tâches que personne n'a jamais questionnées",
        "Recruter ou mieux s'organiser : comment trancher avec des chiffres",
        "Les primes et objectifs que personne ne peut vérifier",
        "Ce qui se passe quand la personne qui tient la compta part en congés",
    ],
    "operations": [
        "Le stock qui dort et immobilise de la trésorerie",
        "Les ruptures de stock qui font perdre des ventes sans que personne ne les compte",
        "Les achats passés au fil de l'eau sans comparer les fournisseurs",
        "La hausse des prix fournisseurs que les prix de vente n'ont pas suivie",
        "Les retards de livraison qui coûtent plus que le transport",
        "Le taux d'utilisation des machines : ce qui tourne vraiment",
        "Les pertes, la casse et les invendus que personne ne chiffre",
        "Savoir ce que coûte réellement une heure de production",
        "Les chantiers ou projets qui dépassent le budget sans alerte",
        "Inventaire annuel : découvrir l'écart une fois par an, c'est trop tard",
        "Les commandes urgentes qui désorganisent tout le planning",
        "Le fournisseur unique dont tout dépend",
    ],
    "outils": [
        "Le tableau Excel devenu impossible à modifier sans tout casser",
        "Le reporting mensuel qui prend 2 jours à préparer",
        "Les relances clients qui pourraient partir toutes seules",
        "Un tableau de bord mis à jour chaque matin sans intervention",
        "Les logiciels achetés qui ne parlent pas entre eux",
        "Quand passer d'Excel à un vrai tableau de bord",
        "Un outil sur mesure ou un logiciel du marché : comment choisir",
        "Ce que l'IA fait déjà bien dans une petite entreprise, et ce qu'elle ne fait pas",
        "Les factures fournisseurs saisies à la main une par une",
        "Le suivi des projets dispersé entre mails, carnets et fichiers",
        "Trois indicateurs sur un écran plutôt que 40 onglets",
        "Les chiffres que le dirigeant demande et qu'il faut une demi-journée pour sortir",
    ],
    "dirigeant": [
        "Décider le soir sur des chiffres qui datent du mois dernier",
        "Les 5 chiffres qu'un dirigeant devrait voir chaque lundi matin",
        "Le budget fait en janvier qui ne sert plus à rien en mars",
        "Ouvrir un deuxième site ou une nouvelle activité : les chiffres à regarder avant",
        "Préparer la vente ou la transmission de son entreprise plusieurs années avant",
        "Ce qu'il faut demander à son expert-comptable et ce qu'il ne fera pas à votre place",
        "Grandir trop vite : quand la croissance vide la trésorerie",
        "Passer de chef d'entreprise qui fait tout à dirigeant qui pilote",
        "Les décisions prises au feeling qui auraient pu être vérifiées en 10 minutes",
        "Quand se faire accompagner, et sur quoi exactement",
        "Traverser une baisse d'activité : ce qu'il faut regarder en premier",
        "Réorganiser son entreprise sans casser ce qui marche",
    ],
}

HISTORY_FILE = Path(__file__).parent / "data" / "topics_history.json"
HISTORY_SIZE = 40           # sujets récents à ne pas reprendre
RECENT_DOMAINS = 2          # domaines récents évités au tirage suivant

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
        "Génère un post qui réagit à une actualité récente ou tendance du moment qui touche la vie des PME (réglementation, économie, banque, emploi, outils, IA).\n"
        "Prends une position claire et argumentée. Ton : expert, réactif, pertinent.\n"
        "Structure : accroche sur l'actualité → analyse → implication concrète → clôture.\n"
        "Exemples d'angles : réforme réglementaire, taux et crédit, prix de l'énergie, recrutement, nouvel usage de l'IA.\n"
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
    theme = LEGACY_THEMES.get(theme, theme)
    prompt_file = THEMES.get(theme) or THEMES[THEME_NAME]
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
    """Thème unique."""
    return THEME_NAME


def _load_history() -> dict:
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"posts": [], "carousels": []}


def _save_history(history: dict) -> None:
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        for key in ("posts", "carousels"):
            history[key] = history.get(key, [])[-HISTORY_SIZE:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Historique sujets non sauvegardé : {e}")


def pick_topic(domain: Optional[str] = None) -> Tuple[str, str]:
    """
    Tire (domaine, sujet) en évitant les domaines et sujets récents.
    domain : clé de DOMAINS pour forcer un domaine, sinon tirage.
    """
    history = _load_history()
    recent = history.get("posts", [])
    used = {h.get("topic") for h in recent}

    if domain not in FORCED_TOPICS:
        recent_domains = [h.get("domain") for h in recent[-RECENT_DOMAINS:]]
        choices = [d for d in FORCED_TOPICS if d not in recent_domains] or list(FORCED_TOPICS)
        domain = random.choice(choices)

    fresh = [t for t in FORCED_TOPICS[domain] if t not in used] or FORCED_TOPICS[domain]
    topic = random.choice(fresh)

    recent.append({"domain": domain, "topic": topic})
    history["posts"] = recent
    _save_history(history)
    return domain, topic


def pick_from(pool: list, kind: str = "carousels") -> str:
    """Tire un élément d'une liste en évitant les derniers utilisés (ex : sujets de carrousel)."""
    history = _load_history()
    used = set(history.get(kind, []))
    item = random.choice([x for x in pool if x not in used] or pool)
    history.setdefault(kind, []).append(item)
    _save_history(history)
    return item


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
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


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


# ─── Garde-fou de longueur ────────────────────────────────────────────────────

MAX_POST_CHARS = 1000


def _enforce_length(post: str, system_prompt: str) -> str:
    """Si le post dépasse la limite, demande à Claude de le resserrer (une seule fois)."""
    if len(post) <= MAX_POST_CHARS:
        return post
    logger.info(f"Post trop long ({len(post)} signes) : resserrage")
    user_message = (
        f"Ce post fait {len(post)} signes. Ramène-le sous {MAX_POST_CHARS} signes, hashtags compris.\n"
        "Garde le hook, le chiffre central et la clôture. Supprime des idées entières plutôt que de "
        "raccourcir chaque phrase. Garde le même ton, les mêmes règles, et les retours à la ligne.\n"
        "Retourne uniquement le post.\n\n"
        f"{post}"
    )
    try:
        shorter, _ = _call_llm(system_prompt, user_message, force_provider="claude")
        return shorter if len(shorter) < len(post) else post
    except Exception as e:
        logger.warning(f"Resserrage impossible : {e}")
        return post


# ─── Génération d'un post ─────────────────────────────────────────────────────

def generate_post(theme: Optional[str] = None, custom_brief: Optional[str] = None, post_type: Optional[str] = None,
                  domain: Optional[str] = None) -> Tuple[str, str]:
    """
    Génère un post LinkedIn.

    Args:
        theme: clé du thème (tiré au sort si None)
        custom_brief: sujet libre fourni via /brief
        post_type: 'general', 'personal' ou 'news' (tiré au sort si None)
        domain: clé de DOMAINS pour forcer un domaine (tiré au sort si None)

    Returns:
        (contenu du post, thème utilisé)
    """
    theme = pick_theme()

    if not post_type:
        post_type = pick_post_type()

    system_prompt = load_prompt(theme)
    type_instruction = POST_TYPE_INSTRUCTIONS[post_type]

    if custom_brief:
        forced_subject, domain_label = custom_brief, "libre"
    else:
        # Domaine + sujet tirés au sort, en évitant les derniers utilisés
        domain, forced_subject = pick_topic(domain)
        domain_label = DOMAINS[domain]

    user_message = (
        f"{type_instruction}\n\n"
        f"DOMAINE : {domain_label}\n"
        f"SUJET OBLIGATOIRE : {forced_subject}\n\n"
        "Traite EXACTEMENT ce sujet - n'en change pas.\n"
        "Trouve un angle original et une accroche forte.\n"
        "Reste concret, direct, évite les généralités.\n"
        "Zéro jargon technique (pas de data warehouse, base SQL, table, API, ETL, pipeline, script) : "
        "traduis chaque notion en ce que le dirigeant voit ou gagne."
    )

    logger.info(f"Génération | domaine : {domain_label} | sujet : {forced_subject} | type : {post_type}")
    post, provider = _call_llm(system_prompt, user_message)
    post = _enforce_length(post, system_prompt)
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
    theme = pick_theme()

    post_type = pick_post_type()
    system_prompt = load_prompt(theme)
    type_instruction = POST_TYPE_INSTRUCTIONS[post_type]

    if previous_post:
        user_message = (
            f"{type_instruction}\n\n"
            "Génère un post COMPLÈTEMENT DIFFÉRENT du précédent.\n\n"
            f"Post précédent à ne pas reproduire :\n{previous_post[:400]}...\n\n"
            "Change l'angle, le sujet, le style. Choisis un autre domaine de la vie de l'entreprise "
            "(argent, clients, équipe, achats et stocks, outils, décisions du dirigeant). "
            "Ne reprends aucune formulation.\n"
            "Zéro jargon technique : traduis chaque notion en ce que le dirigeant voit ou gagne."
        )
    else:
        domain, subject = pick_topic()
        user_message = (
            f"{type_instruction}\n\n"
            f"DOMAINE : {DOMAINS[domain]}\nSUJET OBLIGATOIRE : {subject}\n\n"
            "Trouve un angle frais et une accroche qui sort du lot.\n"
            "Zéro jargon technique : traduis chaque notion en ce que le dirigeant voit ou gagne."
        )

    logger.info(f"Nouveau post | thème : {theme} | type : {post_type}")
    post, provider = _call_llm(system_prompt, user_message)
    post = _enforce_length(post, system_prompt)
    logger.info(f"Nouveau post généré ({len(post.split())} mots) via {provider.upper()}")
    return post, theme
