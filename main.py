"""
main.py
Point d'entrée principal du bot LinkedIn Automation.

Lance en simultané :
  - Le bot Telegram (long-polling)
  - Le scheduler APScheduler (génération automatique 3x/semaine)

Usage :
  python main.py
"""

import asyncio
import logging
import signal
import sys

from config import validate_config

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("linkedin_bot.log", encoding="utf-8"),
    ],
)
# Masque les URL Telegram (qui contiennent le token) dans les logs
for _noisy in ("httpx", "httpx2", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    # 1. Valider la configuration avant de démarrer quoi que ce soit
    errors = validate_config()
    if errors:
        for err in errors:
            logger.error(f"Config manquante : {err}")
        logger.error("Corrige ton fichier .env puis relance main.py")
        sys.exit(1)

    logger.info("─" * 60)
    logger.info("🚀  LinkedIn Automation Bot — démarrage")
    logger.info("─" * 60)

    # 2. Construire l'application Telegram
    from telegram_bot import build_application

    application = build_application()

    # 3. Configurer le scheduler
    from scheduler import setup_scheduler

    scheduler = setup_scheduler(application)

    # 4. Initialiser et démarrer l'application Telegram
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    # 5. Démarrer le scheduler
    scheduler.start()

    logger.info("✅ Bot Telegram en écoute")
    logger.info("✅ Scheduler actif")
    logger.info("   → Envoie /start sur Telegram pour commencer")

    # 6. Boucle principale — attendre le signal d'arrêt
    stop_event = asyncio.Event()

    def _handle_signal(sig, frame) -> None:
        logger.info(f"Signal {sig} reçu — arrêt propre en cours...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    await stop_event.wait()

    # 7. Shutdown propre
    logger.info("🛑 Arrêt du scheduler...")
    scheduler.shutdown(wait=False)

    logger.info("🛑 Arrêt du bot Telegram...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

    logger.info("✅ Arrêt propre effectué. À bientôt !")


if __name__ == "__main__":
    asyncio.run(main())
