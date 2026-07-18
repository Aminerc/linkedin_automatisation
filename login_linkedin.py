"""
login_linkedin.py
Script à exécuter UNE SEULE FOIS depuis ta machine locale (pas le serveur).

Il ouvre un vrai navigateur Chrome visible, tu te connectes manuellement
à LinkedIn, puis les cookies de session sont sauvegardés dans cookies/linkedin_cookies.json.

Ensuite, tu copies ce fichier cookies/ sur ton serveur Oracle Cloud.

Usage :
  python login_linkedin.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from playwright.async_api import async_playwright

COOKIES_FILE = Path(__file__).parent / "cookies" / "linkedin_cookies.json"

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


async def manual_login() -> None:
    print()
    print("=" * 62)
    print("   🔑  SESSION DE CONNEXION LINKEDIN MANUELLE")
    print("=" * 62)
    print()
    print("  1. Un navigateur Chrome va s'ouvrir.")
    print("  2. Connecte-toi à LinkedIn normalement (email + mot de passe).")
    print("  3. Une fois sur ton fil d'actualité (Feed), reviens ici.")
    print("  4. Appuie sur ENTRÉE → les cookies seront sauvegardés.")
    print()
    input("  ▶  Appuie sur ENTRÉE pour lancer le navigateur...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--window-size=1280,900", "--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        print()
        print("  ✅  Navigateur ouvert → connecte-toi à LinkedIn.")
        print("  ⏳  En attente... (reviens ici une fois sur le Feed)")
        print()
        input("  ▶  Appuie sur ENTRÉE une fois que tu es sur le Feed LinkedIn...")

        current_url = page.url
        print(f"\n  URL actuelle : {current_url}")

        if "linkedin.com/login" in current_url or "linkedin.com/checkpoint" in current_url:
            print()
            print("  ⚠️  Tu ne sembles pas être connecté (toujours sur la page de login).")
            print("     Assure-toi d'être bien sur le Feed avant de continuer.")
            choice = input("  Continuer quand même ? (o/n) : ").strip().lower()
            if choice != "o":
                await browser.close()
                print("  Annulé.")
                return

        # Sauvegarder les cookies
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        cookies = await context.cookies()

        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        await browser.close()

    print()
    print("=" * 62)
    print(f"  ✅  {len(cookies)} cookies sauvegardés")
    print(f"      → {COOKIES_FILE}")
    print()
    print("  PROCHAINE ÉTAPE — copier les cookies sur Oracle Cloud :")
    print()
    print("    scp -r cookies/ ubuntu@<IP_SERVEUR>:~/linkedin_automation/")
    print()
    print("  Ensuite lance le bot sur le serveur :")
    print("    sudo systemctl start linkedin_bot")
    print("=" * 62)
    print()


if __name__ == "__main__":
    asyncio.run(manual_login())
