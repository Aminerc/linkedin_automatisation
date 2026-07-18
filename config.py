"""
config.py
Centralise toute la configuration du projet LinkedIn Automation.
Les valeurs sont chargées depuis le fichier .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# ─── API Keys ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: int = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

# ─── LinkedIn ────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")
LINKEDIN_COOKIES_FILE: Path = BASE_DIR / "cookies" / "linkedin_cookies.json"
# ID numérique LinkedIn — si renseigné, évite l'appel /voyager/api/me à chaque post
# Pour le trouver : lancer get_person_id.py ou voir les logs après un post
LINKEDIN_PERSON_ID: str = os.getenv("LINKEDIN_PERSON_ID", "")
# Token OAuth officiel LinkedIn (scope w_member_social) — généré par get_linkedin_token.py
LINKEDIN_ACCESS_TOKEN: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")

# ─── Branding des visuels ────────────────────────────────────────────────────
# Nom et tagline affichés sur les images et carrousels générés
BRAND_NAME: str = os.getenv("BRAND_NAME", "Votre Nom")
BRAND_TAGLINE: str = os.getenv("BRAND_TAGLINE", "Automatisation & Data pour la finance")

# ─── Scheduler ───────────────────────────────────────────────────────────────
# Jours de publication : lun, mer, ven par défaut
SCHEDULE_DAYS: list[str] = ["mon", "wed", "fri"]
SCHEDULE_HOUR: int = 8       # heure de déclenchement (Paris)
SCHEDULE_MINUTE: int = 30    # minute de déclenchement

# ─── Contenu ─────────────────────────────────────────────────────────────────
# Les thèmes et leurs prompts sont définis dans content_generator.py
# et lus depuis prompts/theme_finance_compta.md et prompts/theme_tech_ia.md

# ─── Modèles ─────────────────────────────────────────────────────────────────
CLAUDE_MODEL: str = "claude-opus-4-6"
PERPLEXITY_MODEL: str = "sonar-pro"   # alternatives : "sonar", "sonar-reasoning"

# ─── Poids des providers (doivent totaliser 1.0) ─────────────────────────────
# Augmente PERPLEXITY_WEIGHT pour réduire la conso Claude API
PROVIDER_WEIGHTS: dict[str, float] = {
    "claude":     0.30,   # 30% des appels
    "perplexity": 0.70,   # 70% des appels
}

# ─── Playwright ──────────────────────────────────────────────────────────────
HEADLESS: bool = True   # False uniquement pour debug local


def validate_config() -> list[str]:
    """Vérifie que les variables d'env critiques sont présentes. Retourne la liste des erreurs."""
    errors = []
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY manquante dans .env")
    if not PERPLEXITY_API_KEY:
        errors.append("PERPLEXITY_API_KEY manquante dans .env")
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN manquant dans .env")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID manquant dans .env")
    return errors
