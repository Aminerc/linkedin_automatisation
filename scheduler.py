"""
scheduler.py
Planifie la génération automatique de posts LinkedIn.

Planning :
  - Lundi  8h30 → post texte + image DALL-E
  - Mercredi 8h00 → carousel PDF (5 slides)
  - Vendredi 8h30 → post texte + image DALL-E
"""

import logging
import random
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from config import TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


# ─── Job : post texte + image ─────────────────────────────────────────────────

async def _generate_text_post(application: Application) -> None:
    """
    Génère un post texte + image DALL-E et l'envoie sur Telegram pour validation.
    """
    logger.info("⏰ Déclenchement planifié — post texte + image")

    try:
        from content_generator import generate_post
        from image_generator import generate_post_image
        from telegram_bot import send_post_for_approval

        content, theme = generate_post()
        logger.info(f"Post généré | thème : {theme}")

        # Générer l'image DALL-E
        image_bytes: Optional[bytes] = None
        try:
            image_bytes = generate_post_image(theme, content)
            logger.info("Image DALL-E générée avec succès")
        except Exception as img_err:
            logger.warning(f"Génération image échouée (post texte seul) : {img_err}")

        await send_post_for_approval(
            application,
            content,
            theme,
            image_bytes=image_bytes,
        )

    except Exception as e:
        logger.error(f"Erreur génération post texte : {e}")
        await _notify_error(application, str(e))


# ─── Job : carousel mercredi ──────────────────────────────────────────────────

async def _generate_carousel(application: Application) -> None:
    """
    Génère un carousel PDF et l'envoie sur Telegram pour validation.
    """
    logger.info("⏰ Déclenchement planifié — carousel LinkedIn")

    try:
        from carousel_generator import generate_carousel_content, create_carousel_pdf
        from telegram_bot import send_carousel_for_approval

        carousel_data = generate_carousel_content()
        pdf_bytes = create_carousel_pdf(carousel_data)

        logger.info(
            f"Carousel généré | sujet : {carousel_data['subject']} | "
            f"PDF : {len(pdf_bytes) // 1024} KB"
        )

        await send_carousel_for_approval(application, carousel_data, pdf_bytes)

    except Exception as e:
        logger.error(f"Erreur génération carousel : {e}")
        await _notify_error(application, str(e))


async def _notify_error(application: Application, error_msg: str) -> None:
    """Notifie l'erreur via Telegram."""
    try:
        await application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"⚠️ *Erreur planification*\n\n`{error_msg}`",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ─── Setup du scheduler ───────────────────────────────────────────────────────

def setup_scheduler(application: Application) -> AsyncIOScheduler:
    """Configure et retourne le scheduler APScheduler."""
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")

    # Décalage aléatoire ±20 min pour humaniser le timing (posts texte)
    offset = random.randint(-20, 20)
    raw_min = 30 + offset
    hour_adj = 8 + (raw_min // 60)
    final_min = raw_min % 60
    final_hour = hour_adj % 24

    # Lundi — post texte + image
    scheduler.add_job(
        _generate_text_post,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=final_hour,
            minute=final_min,
            timezone="Europe/Paris",
        ),
        args=[application],
        id="linkedin_post_monday",
        name="Post texte LinkedIn — Lundi",
        misfire_grace_time=3600,
        replace_existing=True,
        coalesce=True,
    )

    # Mercredi — carousel (heure fixe 8h00, pas de décalage)
    scheduler.add_job(
        _generate_carousel,
        trigger=CronTrigger(
            day_of_week="wed",
            hour=8,
            minute=0,
            timezone="Europe/Paris",
        ),
        args=[application],
        id="linkedin_carousel_wednesday",
        name="Carousel LinkedIn — Mercredi",
        misfire_grace_time=3600,
        replace_existing=True,
        coalesce=True,
    )

    # Vendredi — post texte + image (même offset que lundi)
    scheduler.add_job(
        _generate_text_post,
        trigger=CronTrigger(
            day_of_week="fri",
            hour=final_hour,
            minute=final_min,
            timezone="Europe/Paris",
        ),
        args=[application],
        id="linkedin_post_friday",
        name="Post texte LinkedIn — Vendredi",
        misfire_grace_time=3600,
        replace_existing=True,
        coalesce=True,
    )

    logger.info(
        f"Scheduler configuré :\n"
        f"  Lun/Ven → post texte + image à {final_hour}h{final_min:02d}\n"
        f"  Mer     → carousel à 8h00"
    )

    return scheduler
