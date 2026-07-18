"""
carousel_generator.py
Génère des carousels LinkedIn au format PDF multi-slides.

Flow :
  1. generate_carousel_content() → Claude génère le contenu structuré (JSON)
  2. create_carousel_pdf()       → reportlab crée le PDF page par page
  3. Chaque page du PDF = 1 slide dans le carousel LinkedIn

Format : 540x540 points (carré, idéal pour LinkedIn mobile)
Style  : slide couverture sombre + slides contenu blanches + slide CTA bleue
"""

import io
import json
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME, BRAND_TAGLINE = "Votre Nom", "Automatisation & Data pour la finance"

# ─── Topics par thème ─────────────────────────────────────────────────────────
CAROUSEL_TOPICS = {
    "Finance, Compta & Gestion": [
        "Les 5 erreurs de trésorerie que font 80% des PME",
        "Facturation électronique 2026 : ce qui change concrètement",
        "Comment passer d'une clôture trimestrielle à mensuelle",
        "P&L en temps réel : les étapes pour y arriver",
        "Optimiser son BFR en 5 étapes concrètes",
        "Les KPIs financiers que tout dirigeant doit suivre",
        "Contrôle de gestion PME : par où commencer",
        "5 signes que votre reporting financier est à refaire",
    ],
    "Tech & IA appliquée à la Finance": [
        "Automatiser son reporting finance en 5 étapes",
        "Power BI pour les équipes finance : guide pratique",
        "Excel vs Power Query : quand passer au niveau sup",
        "Les 5 process finance à automatiser en priorité",
        "IA appliquée à la comptabilité : cas d'usage concrets",
        "Dashboard financier temps réel : comment démarrer",
        "SQL pour les contrôleurs de gestion",
        "Agents IA en finance : ce qui marche vraiment",
    ],
}

# ─── Couleurs — palette Ocean Breeze ───────────────────────────────
C_BG_DARK    = "#2F4858"   # navy fond
C_BLUE       = "#336699"   # accent principal
C_ACCENT     = "#9EE493"   # vert highlight
C_BLUE_LIGHT = "#86BBD8"   # texte secondaire
C_WHITE      = "#FFFFFF"
C_LIGHT      = "#DAF7DC"   # vert pâle
C_TEXT       = "#2F4858"   # texte sur fond clair
C_MUTED      = "#64748B"
C_BORDER     = "#E2E8F0"

# ─── Polices Poppins/Lato (projet, avec fallback Helvetica) ──────────────────
from pathlib import Path as _Path
_FONTS_DIR = _Path(__file__).parent / "fonts"
_AVATAR = _Path(__file__).parent / "avatar.png"


def _register_fonts() -> dict:
    """Enregistre Poppins/Lato dans reportlab. Retourne le mapping des noms."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts = {"bold": "Helvetica-Bold", "medium": "Helvetica-Bold", "regular": "Helvetica"}
    try:
        pdfmetrics.registerFont(TTFont("Poppins-Bold", str(_FONTS_DIR / "Poppins-Bold.ttf")))
        fonts["bold"] = "Poppins-Bold"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("Poppins-Medium", str(_FONTS_DIR / "Poppins-Medium.ttf")))
        fonts["medium"] = "Poppins-Medium"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("Lato", str(_FONTS_DIR / "Lato-Regular.ttf")))
        fonts["regular"] = "Lato"
    except Exception:
        pass
    return fonts


# ─── Génération du contenu ────────────────────────────────────────────────────

def generate_carousel_content(theme: Optional[str] = None, custom_brief: Optional[str] = None) -> dict:
    """
    Génère le contenu structuré du carousel via Claude (toujours Claude pour la structure).

    Args:
        theme: thème du carousel (tiré au sort si None)
        custom_brief: sujet libre (ex: depuis /carousel <sujet>)

    Returns:
        dict avec title, subtitle, intro, slides (list), cta, theme, subject
    """
    from anthropic import Anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
    from content_generator import THEMES

    if not theme:
        theme = random.choice(list(THEMES.keys()))

    if custom_brief:
        subject = custom_brief
    else:
        topics = CAROUSEL_TOPICS.get(theme, CAROUSEL_TOPICS["Finance, Compta & Gestion"])
        subject = random.choice(topics)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    system = """Tu es expert en création de carousels LinkedIn pour professionnels de la finance et de la tech.
Génère un carousel structuré en JSON strict avec ce format EXACT :
{
  "title": "Titre accrocheur (max 7 mots)",
  "subtitle": "Sous-titre clair (max 12 mots)",
  "intro": "Texte du post LinkedIn qui accompagne le carousel (2-3 phrases, accroche forte, pas plus de 60 mots)",
  "slides": [
    {
      "number": "01",
      "title": "Titre slide (max 6 mots)",
      "content": "Développement : 2-3 phrases courtes et concrètes.",
      "emoji": "📊"
    }
  ],
  "cta": "Call to action final (1 phrase directe, max 15 mots)"
}
RÈGLES STRICTES :
- 5 slides de contenu exactement, numérotées "01" à "05"
- Chaque slide = 1 idée forte et actionnable
- Langage direct, concret, professionnel
- RETOURNE UNIQUEMENT LE JSON, sans markdown, sans backticks, sans texte autour"""

    user_msg = f"Crée un carousel LinkedIn sur : {subject}\nThème : {theme}"

    logger.info(f"Génération carousel | sujet : {subject} | thème : {theme}")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()

    # Nettoyer les éventuels backticks markdown
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    data = json.loads(raw)
    data["subject"] = subject
    data["theme"] = theme
    return data


# ─── Carrousel depuis un texte validé ────────────────────────────────────────

def generate_carousel_from_text(post_text: str, theme: str) -> dict:
    """
    Génère 3-4 slides à partir d'un texte de post DÉJÀ validé.
    Les slides reprennent les idées du texte — pas de contenu inventé.
    """
    from anthropic import Anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    system = """Tu es expert en création de carousels LinkedIn pour professionnels de la finance.
On te donne le TEXTE FINAL d'un post LinkedIn. Ta mission : le transformer en carousel.
Génère un JSON strict avec ce format EXACT :
{
  "title": "Titre accrocheur repris du texte (max 7 mots)",
  "subtitle": "Sous-titre clair (max 12 mots)",
  "intro": "",
  "slides": [
    {
      "number": "01",
      "title": "Titre slide (max 6 mots)",
      "content": "2-3 phrases courtes reprenant une idée DU TEXTE.",
      "emoji": "📊"
    }
  ],
  "cta": "Call to action final (1 phrase directe, max 15 mots)"
}
RÈGLES STRICTES :
- 3 ou 4 slides selon la richesse du texte (numérotées "01", "02", ...)
- Chaque slide reprend UNIQUEMENT des idées présentes dans le texte fourni — n'invente rien
- Langage direct, concret, professionnel
- RETOURNE UNIQUEMENT LE JSON, sans markdown, sans backticks, sans texte autour"""

    user_msg = f"Texte du post à transformer en carousel :\n\n{post_text}\n\nThème : {theme}"

    logger.info(f"Génération carousel depuis texte | thème : {theme}")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    data = json.loads(raw)
    data["subject"] = data.get("title", "")
    data["theme"] = theme
    data["intro"] = post_text
    return data


# ─── PDF 1 page (quote card) ─────────────────────────────────────────────────

def create_quote_pdf(theme: str, post_text: str) -> bytes:
    """
    Crée un PDF 1 page à partir de la quote card PNG (image_generator).
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader

    from image_generator import generate_post_image

    png_bytes = generate_post_image(theme, post_text)

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(1200, 630))
    c.drawImage(ImageReader(io.BytesIO(png_bytes)), 0, 0, width=1200, height=630)
    c.showPage()
    c.save()
    logger.info(f"Quote PDF généré ({buf.tell() // 1024} KB)")
    return buf.getvalue()


# ─── Génération du PDF ────────────────────────────────────────────────────────

def create_carousel_pdf(carousel_data: dict) -> bytes:
    """
    Crée un PDF carousel professionnel avec reportlab.
    Chaque page = 1 slide LinkedIn (540x540 points, format carré).

    Args:
        carousel_data: dict retourné par generate_carousel_content()

    Returns:
        bytes du PDF
    """
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    SIZE = 540
    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(SIZE, SIZE))

    fonts = _register_fonts()
    F_BOLD, F_MED, F_REG = fonts["bold"], fonts["medium"], fonts["regular"]

    # Couleurs
    dark_bg    = colors.HexColor(C_BG_DARK)
    blue       = colors.HexColor(C_BLUE)
    accent     = colors.HexColor(C_ACCENT)
    blue_light = colors.HexColor(C_BLUE_LIGHT)
    white      = colors.white
    text       = colors.HexColor(C_TEXT)
    muted      = colors.HexColor(C_MUTED)
    border     = colors.HexColor(C_BORDER)
    light_num  = colors.HexColor("#E2E8F0")

    theme = carousel_data.get("theme", "")
    slides = carousel_data.get("slides", [])
    total_content = len(slides)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def wrap_text(c_obj, text_str, font, size, max_w):
        """Découpe le texte en lignes selon la largeur max."""
        words = str(text_str).split()
        lines, current = [], []
        for w in words:
            current.append(w)
            if c_obj.stringWidth(" ".join(current), font, size) > max_w:
                if len(current) > 1:
                    lines.append(" ".join(current[:-1]))
                    current = [current[-1]]
                else:
                    lines.append(" ".join(current))
                    current = []
        if current:
            lines.append(" ".join(current))
        return lines

    def progress_dots(c_obj, current_idx, total, y=28):
        """Affiche les points de progression."""
        dot_spacing = 14
        start_x = SIZE // 2 - (total * dot_spacing) // 2
        for i in range(total):
            if i == current_idx:
                c_obj.setFillColor(blue)
                c_obj.circle(start_x + i * dot_spacing, y, 5, fill=1, stroke=0)
            else:
                c_obj.setFillColor(border)
                c_obj.circle(start_x + i * dot_spacing, y, 4, fill=1, stroke=0)

    # ── Slide 1 : Couverture ──────────────────────────────────────────────────

    # Fond navy
    c.setFillColor(dark_bg)
    c.rect(0, 0, SIZE, SIZE, fill=1, stroke=0)

    # Barre accent haut (vert)
    c.setFillColor(accent)
    c.rect(0, SIZE - 5, SIZE, 5, fill=1, stroke=0)

    # Cercles décoratifs coin haut-droit (contours)
    c.setStrokeColor(blue_light)
    c.setLineWidth(1.5)
    c.circle(SIZE, SIZE, 90, fill=0, stroke=1)
    c.setStrokeColor(blue)
    c.circle(SIZE, SIZE, 55, fill=0, stroke=1)

    # Kicker thème (vert, souligné)
    kicker = "AUTOMATISATION · DATA & IA" if ("Tech" in theme or "IA" in theme) else "FINANCE & COMPTABILITÉ"
    c.setFillColor(accent)
    c.setFont(F_MED, 12)
    c.drawString(40, SIZE - 60, kicker)
    c.setFillColor(accent)
    c.rect(40, SIZE - 70, 45, 2, fill=1, stroke=0)

    # Titre couverture (Poppins Bold)
    title_lines = wrap_text(c, carousel_data.get("title", ""), F_BOLD, 30, SIZE - 90)
    c.setFillColor(white)
    c.setFont(F_BOLD, 30)
    y_t = SIZE // 2 + 40 + (len(title_lines) - 1) * 18
    for i, line in enumerate(title_lines):
        c.drawString(40, y_t - i * 42, line)

    # Sous-titre (bleu clair)
    sub_y = y_t - len(title_lines) * 42 - 16
    c.setFillColor(blue_light)
    c.setFont(F_REG, 14)
    for line in wrap_text(c, carousel_data.get("subtitle", ""), F_REG, 14, SIZE - 90)[:2]:
        c.drawString(40, sub_y, line)
        sub_y -= 20

    # Avatar coin bas-droit (pleine résolution — le PDF gère l'échelle)
    if _AVATAR.exists():
        try:
            from PIL import Image as _PILImage
            _av = _PILImage.open(_AVATAR).convert("RGBA")
            _av = _av.crop((0, 0, _av.width, int(_av.height * 0.52)))
            _h = 170
            _w = int(_av.width * _h / _av.height)
            c.drawImage(ImageReader(_av), SIZE - _w - 10, 0,
                        width=_w, height=_h, mask="auto")
        except Exception:
            pass

    # Branding + swipe hint
    c.setFillColor(white)
    c.setFont(F_MED, 12)
    c.drawString(40, 52, BRAND_NAME)
    c.setFillColor(blue_light)
    c.setFont(F_REG, 9)
    c.drawString(40, 36, BRAND_TAGLINE)
    c.setFillColor(accent)
    c.setFont(F_REG, 10)
    c.drawString(40, 14, "Swipe →")

    c.showPage()

    # ── Slides contenu ────────────────────────────────────────────────────────

    for idx, slide in enumerate(slides):
        # Fond blanc
        c.setFillColor(white)
        c.rect(0, 0, SIZE, SIZE, fill=1, stroke=0)

        # Barre latérale gauche verte
        c.setFillColor(accent)
        c.rect(0, 0, 5, SIZE, fill=1, stroke=0)

        # Numéro grand (fantôme)
        c.setFillColor(light_num)
        c.setFont(F_BOLD, 90)
        c.drawString(SIZE - 110, SIZE - 100, str(slide.get("number", f"0{idx+1}")))

        # Titre slide (Poppins Bold, navy)
        slide_title = slide.get("title", "")
        title_lines = wrap_text(c, slide_title, F_BOLD, 20, SIZE - 130)
        c.setFillColor(text)
        c.setFont(F_BOLD, 20)
        y_title = SIZE - 90
        for i, line in enumerate(title_lines):
            c.drawString(28, y_title - i * 28, line)

        # Séparateur vert
        sep_y = y_title - len(title_lines) * 28 - 16
        c.setStrokeColor(accent)
        c.setLineWidth(3)
        c.line(28, sep_y, 106, sep_y)

        # Contenu slide (Lato)
        content_str = slide.get("content", "")
        content_lines = wrap_text(c, content_str, F_REG, 14, SIZE - 60)
        c.setFillColor(text)
        c.setFont(F_REG, 14)
        y_content = sep_y - 30
        for i, line in enumerate(content_lines[:9]):
            c.drawString(28, y_content - i * 21, line)

        # Dots progression
        progress_dots(c, idx, total_content)

        c.showPage()

    # ── Slide CTA ─────────────────────────────────────────────────────────────

    # Fond navy
    c.setFillColor(dark_bg)
    c.rect(0, 0, SIZE, SIZE, fill=1, stroke=0)

    # Barre accent haut
    c.setFillColor(accent)
    c.rect(0, SIZE - 5, SIZE, 5, fill=1, stroke=0)

    # Cercles décoratifs (contours)
    c.setStrokeColor(blue)
    c.setLineWidth(1.5)
    c.circle(-30, -30, 130, fill=0, stroke=1)
    c.setStrokeColor(blue_light)
    c.circle(SIZE + 30, SIZE + 30, 130, fill=0, stroke=1)

    # Question CTA (Poppins Bold)
    c.setFillColor(white)
    c.setFont(F_BOLD, 22)
    c.drawCentredString(SIZE // 2, SIZE // 2 + 90, "Vous vous retrouvez dans")
    c.drawCentredString(SIZE // 2, SIZE // 2 + 60, "cette situation ?")

    # Séparateur vert centré
    c.setFillColor(accent)
    c.rect(SIZE // 2 - 40, SIZE // 2 + 38, 80, 3, fill=1, stroke=0)

    # Texte CTA (bleu clair)
    cta_text = carousel_data.get("cta", "Écrivez-moi en DM, on en parle.")
    c.setFillColor(blue_light)
    c.setFont(F_REG, 14)
    cta_lines = wrap_text(c, cta_text, F_REG, 14, SIZE - 80)
    y_cta = SIZE // 2
    for line in cta_lines[:3]:
        c.drawCentredString(SIZE // 2, y_cta, line)
        y_cta -= 21

    # DM ouvert (vert) avec flèche dessinée
    c.setFillColor(accent)
    c.setFont(F_BOLD, 15)
    dm_txt = "DM ouvert"
    dm_w = c.stringWidth(dm_txt, F_BOLD, 15)
    dm_x = SIZE // 2 - dm_w // 2 + 12
    dm_y = y_cta - 16
    c.drawString(dm_x, dm_y, dm_txt)
    # Flèche →
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(dm_x - 28, dm_y + 5, dm_x - 10, dm_y + 5)
    c.line(dm_x - 16, dm_y + 10, dm_x - 10, dm_y + 5)
    c.line(dm_x - 16, dm_y, dm_x - 10, dm_y + 5)

    # Avatar coin bas-droit (pleine résolution — le PDF gère l'échelle)
    if _AVATAR.exists():
        try:
            from PIL import Image as _PILImage
            _av = _PILImage.open(_AVATAR).convert("RGBA")
            _av = _av.crop((0, 0, _av.width, int(_av.height * 0.52)))
            _h = 180
            _w = int(_av.width * _h / _av.height)
            c.drawImage(ImageReader(_av), SIZE - _w - 10, 0,
                        width=_w, height=_h, mask="auto")
        except Exception:
            pass

    # Signature
    c.setFillColor(white)
    c.setFont(F_MED, 12)
    c.drawString(40, 52, BRAND_NAME)
    c.setFillColor(blue_light)
    c.setFont(F_REG, 9)
    c.drawString(40, 36, BRAND_TAGLINE)

    c.showPage()
    c.save()

    return buffer.getvalue()
