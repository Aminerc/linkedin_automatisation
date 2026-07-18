"""
telegram_bot.py
Bot Telegram pour la validation des posts LinkedIn avant publication.

Flow post texte :
  /generate → choisir thème → post + image générés → 4 boutons
  ✅ Publier / ✏️ Modifier / 🔄 Régénérer / ❌ Supprimer

Flow carousel :
  /carousel [sujet] → carousel PDF généré → 3 boutons
  ✅ Publier / 🔄 Régénérer / ❌ Supprimer

Commandes :
  /start           → présentation
  /generate        → sélection thème puis génération post
  /brief <sujet>   → post sur un sujet précis
  /carousel [sujet]→ carousel PDF (sujet optionnel)
  /status          → posts en attente
  /chatid          → ton chat ID
"""

import io
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

# ─── États de conversation ────────────────────────────────────────────────────
WAITING_EDIT_INSTRUCTION = 1
WAITING_DRAFT_EDIT = 2

# ─── États en mémoire ─────────────────────────────────────────────────────────
pending_posts: dict = {}        # message_id → {content, theme, image_bytes, status}
pending_carousels: dict = {}    # message_id → {carousel_data, pdf_bytes, status}


# ─── Claviers inline ──────────────────────────────────────────────────────────

def approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publier", callback_data="approve"),
            InlineKeyboardButton("✏️ Modifier", callback_data="edit"),
        ],
        [
            InlineKeyboardButton("🔄 Régénérer", callback_data="new_post"),
            InlineKeyboardButton("❌ Supprimer", callback_data="cancel"),
        ],
    ])


def carousel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publier le carousel", callback_data="carousel_approve"),
            InlineKeyboardButton("🔄 Régénérer", callback_data="carousel_regen"),
        ],
        [
            InlineKeyboardButton("❌ Supprimer", callback_data="carousel_cancel"),
        ],
    ])


def theme_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Finance & Compta", callback_data="theme_finance"),
            InlineKeyboardButton("🤖 Tech & IA", callback_data="theme_tech"),
        ],
        [
            InlineKeyboardButton("🎲 Aléatoire", callback_data="theme_random"),
        ],
    ])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    return user_id == TELEGRAM_CHAT_ID


def _escape_md(text: str) -> str:
    for ch in ["*", "_", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text


# ─── Envoi post texte pour validation ────────────────────────────────────────

async def send_post_for_approval(
    application: Application,
    content: str,
    theme: str = "",
    image_bytes: Optional[bytes] = None,
) -> int:
    """
    Envoie un post sur Telegram pour validation.
    Si image_bytes fourni, envoie l'image en preview d'abord.
    Retourne le message_id du message avec les boutons.
    """
    # Preview image si disponible
    if image_bytes:
        try:
            await application.bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=io.BytesIO(image_bytes),
                caption=f"🖼️ _Image générée pour ce post_",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Impossible d'envoyer la preview image : {e}")

    header = "📝 *Nouveau post LinkedIn à valider*"
    if theme:
        header += f"\n🏷️ _{theme}_"
    if image_bytes:
        header += "\n🖼️ _Image DALL-E attachée_"

    text = (
        f"{header}\n\n"
        f"───────────────────\n\n"
        f"{content}\n\n"
        f"───────────────────\n\n"
        f"_Que veux-tu faire de ce post ?_"
    )

    msg = await application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=approval_keyboard(),
    )

    pending_posts[msg.message_id] = {
        "content": content,
        "theme": theme,
        "image_bytes": image_bytes,
        "message_id": msg.message_id,
        "status": "pending",
    }

    logger.info(f"Post envoyé pour validation (msg_id={msg.message_id}, image={'oui' if image_bytes else 'non'})")
    return msg.message_id


# ─── Envoi carousel pour validation ──────────────────────────────────────────

async def send_carousel_for_approval(
    application: Application,
    carousel_data: dict,
    pdf_bytes: bytes,
) -> int:
    """
    Envoie un carousel sur Telegram pour validation.
    Envoie d'abord le PDF en aperçu, puis le message avec boutons.
    """
    # Envoyer le PDF en aperçu
    try:
        await application.bot.send_document(
            chat_id=TELEGRAM_CHAT_ID,
            document=InputFile(io.BytesIO(pdf_bytes), filename="carousel_preview.pdf"),
            caption=f"📎 *Aperçu carousel* — _{carousel_data.get('subject', '')}_ ({len(pdf_bytes)//1024} KB)",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Impossible d'envoyer le PDF carousel : {e}")

    # Résumé des slides
    slides = carousel_data.get("slides", [])
    slides_preview = "\n".join(
        f"  {s.get('number', i+1)}. {s.get('emoji','')} {s.get('title','')}"
        for i, s in enumerate(slides)
    )

    intro_escaped = _escape_md(carousel_data.get("intro", ""))

    text = (
        f"🎠 *Carousel LinkedIn à valider*\n"
        f"🏷️ _{carousel_data.get('theme', '')}_\n\n"
        f"*📌 {_escape_md(carousel_data.get('title', ''))}*\n"
        f"_{_escape_md(carousel_data.get('subtitle', ''))}_\n\n"
        f"*Slides :*\n{slides_preview}\n\n"
        f"*Texte du post :*\n{intro_escaped}\n\n"
        f"───────────────────\n"
        f"_Que veux-tu faire de ce carousel ?_"
    )

    msg = await application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=carousel_keyboard(),
    )

    pending_carousels[msg.message_id] = {
        "carousel_data": carousel_data,
        "pdf_bytes": pdf_bytes,
        "status": "pending",
    }

    logger.info(f"Carousel envoyé pour validation (msg_id={msg.message_id})")
    return msg.message_id


# ─── Handlers post texte ──────────────────────────────────────────────────────

async def on_theme_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Génère un post texte + image après sélection du thème."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return

    theme_map = {
        "theme_finance": "Finance, Compta & Gestion",
        "theme_tech": "Tech & IA appliquée à la Finance",
        "theme_random": None,
    }
    label_map = {
        "theme_finance": "💼 Finance & Compta",
        "theme_tech": "🤖 Tech & IA",
        "theme_random": "🎲 Aléatoire",
    }

    theme = theme_map.get(query.data)
    label = label_map.get(query.data, "")

    await query.edit_message_text(
        f"⏳ _Génération en cours — {label}..._",
        parse_mode="Markdown",
    )

    try:
        from content_generator import generate_post
        from image_generator import generate_post_image

        content, theme_used = generate_post(theme=theme)

        image_bytes: Optional[bytes] = None
        try:
            image_bytes = generate_post_image(theme_used, content)
        except Exception as e:
            logger.warning(f"Image non générée : {e}")

        await query.delete_message()
        await send_post_for_approval(context.application, content, theme_used, image_bytes)

    except Exception as e:
        await query.edit_message_text(f"❌ Erreur : {e}")


async def on_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Publie le post texte (+ image) sur LinkedIn."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return

    msg_id = query.message.message_id
    post = pending_posts.get(msg_id)
    if not post:
        await query.edit_message_text("⚠️ Post introuvable ou déjà traité.")
        return

    await query.edit_message_text("⏳ *Publication en cours sur LinkedIn...*", parse_mode="Markdown")

    from linkedin_poster import post_to_linkedin
    result = await post_to_linkedin(post["content"], image_bytes=post.get("image_bytes"))

    if result["success"]:
        pending_posts[msg_id]["status"] = "published"
        preview = _escape_md(post["content"][:200])
        await query.edit_message_text(
            f"✅ *Post publié !*\n\n_{preview}..._",
            parse_mode="Markdown",
        )
    else:
        pending_posts[msg_id]["status"] = "error"
        await query.edit_message_text(
            f"❌ *Erreur de publication*\n\n{result['message']}",
            parse_mode="Markdown",
        )


async def on_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lance le mode modification ciblée."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return ConversationHandler.END

    msg_id = query.message.message_id
    post = pending_posts.get(msg_id)
    if not post:
        await query.edit_message_text("⚠️ Post introuvable.")
        return ConversationHandler.END

    context.user_data["editing_msg_id"] = msg_id
    original_preview = _escape_md(post["content"])
    await query.edit_message_text(
        f"✏️ *Mode modification ciblée*\n\n"
        f"```\n{original_preview}\n```\n\n"
        f"Décris la modification. Exemples :\n"
        f"• _\"remplace 15 par 13\"_\n"
        f"• _\"rends le ton moins commercial\"_\n"
        f"• _\"reformule la conclusion\"_\n\n"
        f"Envoie `/cancel\\_edit` pour annuler.",
        parse_mode="Markdown",
    )
    return WAITING_EDIT_INSTRUCTION


async def receive_edit_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Applique la modification ciblée et re-présente le post."""
    editing_id = context.user_data.get("editing_msg_id")
    if not editing_id or editing_id not in pending_posts:
        await update.message.reply_text("⚠️ Aucun post en cours d'édition.")
        return ConversationHandler.END

    instruction = update.message.text
    original = pending_posts[editing_id]["content"]
    theme = pending_posts[editing_id].get("theme", "")
    image_bytes = pending_posts[editing_id].get("image_bytes")

    wait_msg = await update.message.reply_text(
        f"⏳ _Application : « {instruction} »..._",
        parse_mode="Markdown",
    )

    try:
        from content_generator import edit_post
        modified_content = edit_post(original, instruction, theme)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Erreur modification : {e}")
        return ConversationHandler.END

    await wait_msg.delete()
    context.user_data.pop("editing_msg_id", None)
    pending_posts[editing_id]["content"] = modified_content

    text = (
        f"✏️ *Post modifié — à valider*\n\n"
        f"───────────────────\n\n"
        f"{modified_content}\n\n"
        f"───────────────────\n\n"
        f"_Que veux-tu faire de ce post ?_"
    )

    new_msg = await update.message.reply_text(text, parse_mode="Markdown", reply_markup=approval_keyboard())
    post_data = pending_posts.pop(editing_id)
    post_data["message_id"] = new_msg.message_id
    pending_posts[new_msg.message_id] = post_data
    return ConversationHandler.END


async def on_new_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Régénère un post texte + image (même thème)."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return

    msg_id = query.message.message_id
    post = pending_posts.get(msg_id)
    if not post:
        await query.edit_message_text("⚠️ Post introuvable.")
        return

    await query.edit_message_text("🔄 _Régénération en cours..._", parse_mode="Markdown")

    try:
        from content_generator import new_post
        from image_generator import generate_post_image

        new_content, new_theme = new_post(previous_post=post["content"], theme=post.get("theme"))

        image_bytes: Optional[bytes] = None
        try:
            image_bytes = generate_post_image(new_theme, new_content)
        except Exception as e:
            logger.warning(f"Image non générée : {e}")

        # Si image, envoyer d'abord la photo
        if image_bytes:
            try:
                await context.application.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=io.BytesIO(image_bytes),
                    caption="🖼️ _Nouvelle image générée_",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        text = (
            f"🔄 *Post régénéré — à valider*\n🏷️ _{new_theme}_\n\n"
            f"───────────────────\n\n"
            f"{new_content}\n\n"
            f"───────────────────\n\n"
            f"_Que veux-tu faire de ce post ?_"
        )

        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=approval_keyboard())
        pending_posts[msg_id]["content"] = new_content
        pending_posts[msg_id]["theme"] = new_theme
        pending_posts[msg_id]["image_bytes"] = image_bytes
        pending_posts[msg_id]["status"] = "pending"

    except Exception as e:
        await query.edit_message_text(f"❌ Erreur : {e}")


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Supprime le post texte."""
    query = update.callback_query
    await query.answer()
    msg_id = query.message.message_id
    if msg_id in pending_posts:
        pending_posts[msg_id]["status"] = "cancelled"
    await query.edit_message_text(
        "❌ Post supprimé.\n_Prochain post au prochain créneau planifié._",
        parse_mode="Markdown",
    )


# ─── Handlers carousel ────────────────────────────────────────────────────────

async def on_carousel_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Publie le carousel sur LinkedIn."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return

    msg_id = query.message.message_id
    item = pending_carousels.get(msg_id)
    if not item:
        await query.edit_message_text("⚠️ Carousel introuvable ou déjà traité.")
        return

    await query.edit_message_text("⏳ *Publication du carousel en cours...*", parse_mode="Markdown")

    from linkedin_poster import post_carousel_to_linkedin

    carousel_data = item["carousel_data"]
    result = await post_carousel_to_linkedin(
        content=carousel_data.get("intro", ""),
        pdf_bytes=item["pdf_bytes"],
        title=carousel_data.get("title", "Carousel LinkedIn"),
    )

    if result["success"]:
        pending_carousels[msg_id]["status"] = "published"
        await query.edit_message_text(
            f"✅ *Carousel publié !*\n\n📌 _{_escape_md(carousel_data.get('title',''))}_",
            parse_mode="Markdown",
        )
    else:
        pending_carousels[msg_id]["status"] = "error"
        await query.edit_message_text(
            f"❌ *Erreur carousel*\n\n{result['message']}",
            parse_mode="Markdown",
        )


async def on_carousel_regen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Régénère un nouveau carousel."""
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        await query.answer("⛔ Non autorisé.", show_alert=True)
        return

    msg_id = query.message.message_id
    item = pending_carousels.get(msg_id)
    if not item:
        await query.edit_message_text("⚠️ Carousel introuvable.")
        return

    theme = item["carousel_data"].get("theme")
    await query.edit_message_text("🔄 _Génération d'un nouveau carousel..._", parse_mode="Markdown")

    try:
        from carousel_generator import generate_carousel_content, create_carousel_pdf

        new_data = generate_carousel_content(theme=theme)
        new_pdf = create_carousel_pdf(new_data)

        # Envoyer le nouveau PDF en aperçu
        try:
            await context.application.bot.send_document(
                chat_id=TELEGRAM_CHAT_ID,
                document=InputFile(io.BytesIO(new_pdf), filename="carousel_preview.pdf"),
                caption=f"📎 *Nouveau carousel* — _{new_data.get('subject', '')}_",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        slides = new_data.get("slides", [])
        slides_preview = "\n".join(
            f"  {s.get('number', i+1)}. {s.get('emoji','')} {s.get('title','')}"
            for i, s in enumerate(slides)
        )
        intro_escaped = _escape_md(new_data.get("intro", ""))

        text = (
            f"🎠 *Carousel régénéré — à valider*\n"
            f"🏷️ _{new_data.get('theme', '')}_\n\n"
            f"*📌 {_escape_md(new_data.get('title', ''))}*\n"
            f"_{_escape_md(new_data.get('subtitle', ''))}_\n\n"
            f"*Slides :*\n{slides_preview}\n\n"
            f"*Texte du post :*\n{intro_escaped}\n\n"
            f"───────────────────\n"
            f"_Que veux-tu faire de ce carousel ?_"
        )

        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=carousel_keyboard())
        pending_carousels[msg_id]["carousel_data"] = new_data
        pending_carousels[msg_id]["pdf_bytes"] = new_pdf
        pending_carousels[msg_id]["status"] = "pending"

    except Exception as e:
        await query.edit_message_text(f"❌ Erreur : {e}")


async def on_carousel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Supprime le carousel."""
    query = update.callback_query
    await query.answer()
    msg_id = query.message.message_id
    if msg_id in pending_carousels:
        pending_carousels[msg_id]["status"] = "cancelled"
    await query.edit_message_text(
        "❌ Carousel supprimé.\n_Prochain carousel mercredi 8h._",
        parse_mode="Markdown",
    )


# ─── Commandes ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *LinkedIn Automation Bot*\n\n"
        "Je génère et publie tes posts LinkedIn automatiquement.\n\n"
        "*Commandes :*\n"
        "• `/generate` — choix du thème puis génération\n"
        "• `/brief <sujet>` — génère sur un sujet précis\n"
        "• `/carousel [sujet]` — génère un carousel PDF\n"
        "• `/status` — posts en attente\n"
        "• `/chatid` — ton chat ID\n\n"
        "*Planning automatique :*\n"
        "• Lun/Ven → post texte + image DALL-E\n"
        "• Mer → carousel PDF 5 slides\n\n"
        "*Distribution :*\n"
        "75% fond · 15% expérience · 10% actualité",
        parse_mode="Markdown",
    )


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "📝 *Quel thème pour ce post ?*",
        parse_mode="Markdown",
        reply_markup=theme_keyboard(),
    )


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return
    brief = " ".join(context.args) if context.args else None
    if not brief:
        await update.message.reply_text(
            "Donne-moi un brief. Exemple :\n"
            "`/brief Facturation électronique : ce qui change en 2026 pour les PME`",
            parse_mode="Markdown",
        )
        return

    msg = await update.message.reply_text(
        f"⏳ _Génération en cours pour : {brief}_",
        parse_mode="Markdown",
    )
    try:
        from content_generator import generate_post
        from image_generator import generate_post_image

        content, theme = generate_post(custom_brief=brief)
        image_bytes: Optional[bytes] = None
        try:
            image_bytes = generate_post_image(theme)
        except Exception as e:
            logger.warning(f"Image non générée : {e}")

        await msg.delete()
        await send_post_for_approval(context.application, content, theme, image_bytes)
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")


async def cmd_carousel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Génère un carousel sur un sujet optionnel."""
    if not _is_authorized(update):
        return

    brief = " ".join(context.args) if context.args else None
    subject_info = f" sur : _{brief}_" if brief else ""

    msg = await update.message.reply_text(
        f"⏳ _Génération du carousel{subject_info}..._",
        parse_mode="Markdown",
    )

    try:
        from carousel_generator import generate_carousel_content, create_carousel_pdf

        carousel_data = generate_carousel_content(custom_brief=brief)
        pdf_bytes = create_carousel_pdf(carousel_data)

        await msg.delete()
        await send_carousel_for_approval(context.application, carousel_data, pdf_bytes)

    except Exception as e:
        await msg.edit_text(f"❌ Erreur carousel : {e}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["📊 *Posts en mémoire :*\n"]
    if pending_posts:
        for mid, data in pending_posts.items():
            excerpt = _escape_md(data["content"][:50])
            img = "🖼️" if data.get("image_bytes") else "📝"
            lines.append(f"• `{mid}` {img} [{data['status']}] — {excerpt}…")
    if pending_carousels:
        for mid, data in pending_carousels.items():
            title = _escape_md(data["carousel_data"].get("title", "")[:40])
            lines.append(f"• `{mid}` 🎠 [{data['status']}] — {title}")
    if len(lines) == 1:
        await update.message.reply_text("Aucun post en attente.")
        return
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Ton chat ID : `{update.effective_user.id}`",
        parse_mode="Markdown",
    )


async def cmd_cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("editing_msg_id", None)
    await update.message.reply_text("Édition annulée.")
    return ConversationHandler.END


# ─── Flow /new : type → thème → texte → visuel → publication ─────────────────

draft: dict = {}   # un seul draft actif à la fois


def type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Texte seul", callback_data="d_type_text")],
        [InlineKeyboardButton("📄 Texte + PDF (1 page)", callback_data="d_type_pdf")],
        [InlineKeyboardButton("🎠 Texte + Carrousel (3-4 slides)", callback_data="d_type_carousel")],
    ])


def draft_theme_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Finance & Comptabilité", callback_data="d_theme_finance")],
        [InlineKeyboardButton("🤖 Outils, Data & IA", callback_data="d_theme_tech")],
    ])


def text_validation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Valider le texte", callback_data="d_text_ok"),
            InlineKeyboardButton("✏️ Modifier", callback_data="d_text_edit"),
        ],
        [InlineKeyboardButton("❌ Refuser (annule tout)", callback_data="d_abort")],
    ])


def visual_validation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Valider le visuel", callback_data="d_vis_ok"),
            InlineKeyboardButton("🔄 Régénérer", callback_data="d_vis_regen"),
        ],
        [InlineKeyboardButton("❌ Refuser (annule tout)", callback_data="d_abort")],
    ])


def publish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Publier sur LinkedIn", callback_data="d_publish"),
            InlineKeyboardButton("❌ Annuler", callback_data="d_abort"),
        ],
    ])


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return
    draft.clear()
    await update.message.reply_text(
        "🆕 *Nouveau post — quel type ?*",
        parse_mode="Markdown",
        reply_markup=type_keyboard(),
    )


async def on_draft_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    draft["type"] = query.data.replace("d_type_", "")
    labels = {"text": "📝 Texte seul", "pdf": "📄 Texte + PDF", "carousel": "🎠 Texte + Carrousel"}
    await query.edit_message_text(
        f"{labels[draft['type']]}\n\n*Quel thème ?*",
        parse_mode="Markdown",
        reply_markup=draft_theme_keyboard(),
    )


async def on_draft_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    if not draft.get("type"):
        await query.edit_message_text("⚠️ Draft expiré. Relance `/new`.", parse_mode="Markdown")
        return

    theme_map = {
        "d_theme_finance": "Finance, Compta & Gestion",
        "d_theme_tech": "Tech & IA appliquée à la Finance",
    }
    draft["theme"] = theme_map[query.data]

    await query.edit_message_text("⏳ _Génération du texte..._", parse_mode="Markdown")
    try:
        from content_generator import generate_post
        content, _ = generate_post(theme=draft["theme"])
        draft["content"] = content
        draft["text_ok"] = False
        draft["visual_ok"] = False
        await query.delete_message()
        await _send_draft_text(context)
    except Exception as e:
        await query.edit_message_text(f"❌ Erreur : {e}")


async def _send_draft_text(context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"📝 *Texte à valider* — _{draft['theme']}_\n\n"
        f"───────────────────\n\n"
        f"{draft['content']}\n\n"
        f"───────────────────"
    )
    msg = await context.application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=text_validation_keyboard(),
    )
    draft["text_msg_id"] = msg.message_id


async def _send_publish_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    type_labels = {"text": "📝 Texte seul", "pdf": "📄 Texte + PDF", "carousel": "🎠 Texte + Carrousel"}
    await context.application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"🟢 *Tout est validé !*\n"
            f"{type_labels[draft['type']]} — _{draft['theme']}_\n\n"
            f"_Prêt à publier ?_"
        ),
        parse_mode="Markdown",
        reply_markup=publish_keyboard(),
    )


async def _generate_and_send_visual(context: ContextTypes.DEFAULT_TYPE) -> None:
    from carousel_generator import (
        create_carousel_pdf,
        create_quote_pdf,
        generate_carousel_from_text,
    )

    if draft["type"] == "carousel":
        data = generate_carousel_from_text(draft["content"], draft["theme"])
        pdf = create_carousel_pdf(data)
        draft["carousel_data"] = data
        caption = f"🎠 *Carrousel à valider* — {len(data.get('slides', []))} slides + couverture + CTA"
        filename = "carousel.pdf"
    else:
        pdf = create_quote_pdf(draft["theme"], draft["content"])
        draft["carousel_data"] = None
        caption = "📄 *PDF 1 page à valider*"
        filename = "post.pdf"

    draft["visual_bytes"] = pdf
    draft["visual_ok"] = False

    msg = await context.application.bot.send_document(
        chat_id=TELEGRAM_CHAT_ID,
        document=InputFile(io.BytesIO(pdf), filename=filename),
        caption=caption,
        parse_mode="Markdown",
        reply_markup=visual_validation_keyboard(),
    )
    draft["visual_msg_id"] = msg.message_id


async def on_draft_text_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    if not draft.get("content"):
        await query.edit_message_text("⚠️ Draft expiré. Relance `/new`.", parse_mode="Markdown")
        return

    draft["text_ok"] = True
    await query.edit_message_reply_markup(None)

    if draft["type"] == "text":
        await _send_publish_summary(context)
    else:
        wait = await context.application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="✅ Texte validé.\n⏳ _Génération du visuel..._",
            parse_mode="Markdown",
        )
        try:
            await _generate_and_send_visual(context)
            await wait.delete()
        except Exception as e:
            await wait.edit_text(f"❌ Erreur visuel : {e}")


async def on_draft_text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return ConversationHandler.END
    if not draft.get("content"):
        await query.edit_message_text("⚠️ Draft expiré. Relance `/new`.", parse_mode="Markdown")
        return ConversationHandler.END

    await query.edit_message_text(
        "✏️ *Modification du texte*\n\n"
        "Décris la modification. Exemples :\n"
        "• _\"remplace 15 par 13\"_\n"
        "• _\"rends le ton moins commercial\"_\n\n"
        "⚠️ _Le visuel sera régénéré après re-validation du texte._\n"
        "Envoie `/cancel\\_edit` pour annuler.",
        parse_mode="Markdown",
    )
    return WAITING_DRAFT_EDIT


async def receive_draft_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not draft.get("content"):
        await update.message.reply_text("⚠️ Aucun draft actif.")
        return ConversationHandler.END

    instruction = update.message.text
    wait = await update.message.reply_text(
        f"⏳ _Application : « {instruction} »..._", parse_mode="Markdown"
    )

    try:
        from content_generator import edit_post
        draft["content"] = edit_post(draft["content"], instruction, draft.get("theme"))
    except Exception as e:
        await wait.edit_text(f"❌ Erreur modification : {e}")
        return ConversationHandler.END

    # Sync : le visuel existant est invalidé
    draft["text_ok"] = False
    draft["visual_ok"] = False
    draft.pop("visual_bytes", None)
    old_vis = draft.pop("visual_msg_id", None)
    if old_vis:
        try:
            await context.application.bot.edit_message_reply_markup(
                chat_id=TELEGRAM_CHAT_ID, message_id=old_vis, reply_markup=None
            )
        except Exception:
            pass

    await wait.delete()
    await _send_draft_text(context)
    return ConversationHandler.END


async def on_draft_vis_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    if not draft.get("visual_bytes"):
        await query.answer("⚠️ Draft expiré. Relance /new.", show_alert=True)
        return

    draft["visual_ok"] = True
    await query.edit_message_reply_markup(None)
    await _send_publish_summary(context)


async def on_draft_vis_regen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    if not draft.get("content"):
        await query.answer("⚠️ Draft expiré. Relance /new.", show_alert=True)
        return

    await query.edit_message_reply_markup(None)
    wait = await context.application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="🔄 _Régénération du visuel..._",
        parse_mode="Markdown",
    )
    try:
        await _generate_and_send_visual(context)
        await wait.delete()
    except Exception as e:
        await wait.edit_text(f"❌ Erreur visuel : {e}")


async def on_draft_publish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update):
        return
    if not draft.get("content"):
        await query.edit_message_text("⚠️ Draft expiré. Relance `/new`.", parse_mode="Markdown")
        return

    await query.edit_message_text("⏳ *Publication en cours sur LinkedIn...*", parse_mode="Markdown")

    if draft["type"] == "text":
        from linkedin_poster import post_to_linkedin
        result = await post_to_linkedin(draft["content"])
    else:
        from linkedin_poster import post_carousel_to_linkedin
        if draft.get("carousel_data"):
            title = draft["carousel_data"].get("title", "Post LinkedIn")
        else:
            title = " ".join(draft["content"].split()[:6])
        result = await post_carousel_to_linkedin(
            content=draft["content"],
            pdf_bytes=draft["visual_bytes"],
            title=title,
        )

    if result["success"]:
        await query.edit_message_text("✅ *Post publié sur LinkedIn !*", parse_mode="Markdown")
        draft.clear()
    else:
        await query.edit_message_text(
            f"❌ *Erreur de publication*\n\n{_escape_md(result['message'])}",
            parse_mode="Markdown",
        )


async def on_draft_abort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    draft.clear()
    await query.edit_message_text(
        "❌ *Post refusé — tout est annulé.*\n_Relance `/new` quand tu veux._",
        parse_mode="Markdown",
    )


# ─── Construction de l'application ───────────────────────────────────────────

def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_edit, pattern="^edit$")],
        states={
            WAITING_EDIT_INSTRUCTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_instruction)
            ]
        },
        fallbacks=[CommandHandler("cancel_edit", cmd_cancel_edit)],
        per_message=False,
        per_user=True,
    )

    draft_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_draft_text_edit, pattern="^d_text_edit$")],
        states={
            WAITING_DRAFT_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_draft_edit)
            ]
        },
        fallbacks=[CommandHandler("cancel_edit", cmd_cancel_edit)],
        per_message=False,
        per_user=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(draft_edit_conv)
    app.add_handler(CallbackQueryHandler(on_draft_type, pattern="^d_type_"))
    app.add_handler(CallbackQueryHandler(on_draft_theme, pattern="^d_theme_"))
    app.add_handler(CallbackQueryHandler(on_draft_text_ok, pattern="^d_text_ok$"))
    app.add_handler(CallbackQueryHandler(on_draft_vis_ok, pattern="^d_vis_ok$"))
    app.add_handler(CallbackQueryHandler(on_draft_vis_regen, pattern="^d_vis_regen$"))
    app.add_handler(CallbackQueryHandler(on_draft_publish, pattern="^d_publish$"))
    app.add_handler(CallbackQueryHandler(on_draft_abort, pattern="^d_abort$"))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_handler(CommandHandler("carousel", cmd_carousel))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(edit_conv)
    app.add_handler(CallbackQueryHandler(on_theme_selected, pattern="^theme_"))
    app.add_handler(CallbackQueryHandler(on_approve, pattern="^approve$"))
    app.add_handler(CallbackQueryHandler(on_new_post, pattern="^new_post$"))
    app.add_handler(CallbackQueryHandler(on_cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(on_carousel_approve, pattern="^carousel_approve$"))
    app.add_handler(CallbackQueryHandler(on_carousel_regen, pattern="^carousel_regen$"))
    app.add_handler(CallbackQueryHandler(on_carousel_cancel, pattern="^carousel_cancel$"))

    return app
