"""
image_generator.py
Visuel de post LinkedIn Optifin Data (Pillow), même style que la couverture des carrousels.

Format : 1080 x 1350 (4:5 portrait, occupe le plus de place dans le fil mobile)
  - Fond clair, chiffre clé en très grand, phrase de sens, affirmation du post
  - Portrait d'Amine en bas à droite (avatar.png à la racine du projet)
  - Police Inter, palette Ocean Breeze

Le contenu (chiffre, légende, affirmation) est extrait du post validé via Claude.
Fallback sans LLM si l'appel échoue.
"""

import io
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME, BRAND_TAGLINE = "Amine Ouardi", "Pilotage financier et outils sur mesure pour les PME"

BASE_DIR = Path(__file__).parent
FONTS_DIR = BASE_DIR / "fonts"
AVATAR_PATH = BASE_DIR / "avatar.png"

# ─── Palette Ocean Breeze ────────────────────────────────────────────────────
INK = (47, 72, 88)          # 2F4858
PRIMARY = (51, 102, 153)    # 336699
SECONDARY = (134, 187, 216) # 86BBD8
ACCENT = (158, 228, 147)    # 9EE493
BG = (245, 247, 249)        # F5F7F9
MUTED = (107, 123, 135)     # 6B7B87
WHITE = (255, 255, 255)

W, H = 1080, 1350

# Contenu du dernier visuel généré (sert de titre au document PDF sur LinkedIn)
LAST_VISUAL: dict = {}
M = 80

_FONTS = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
    "black": "Inter-ExtraBold.ttf",
}
_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
]


def _font(kind: str, size: int):
    from PIL import ImageFont
    for path in [FONTS_DIR / _FONTS[kind], *_FALLBACKS]:
        try:
            return ImageFont.truetype(str(path), size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _kicker_for_theme(theme: str) -> str:
    """Repli si Claude ne fournit pas de bandeau (le bandeau suit normalement le sujet du post)."""
    return "PILOTAGE DE PME"


# ─── Contenu du visuel ───────────────────────────────────────────────────────

def _extract_visual_content(post_content: str) -> Optional[dict]:
    """Demande à Claude le chiffre clé, sa légende et l'affirmation du visuel."""
    try:
        from anthropic import Anthropic
        from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        system = """Tu prépares le visuel qui accompagne un post LinkedIn, à partir du texte du post.
Retourne un JSON strict :
{
  "kicker": "2 à 3 mots sur le sujet du post, ex : Trésorerie · Délais clients, Équipe · Recrutement, Prix · Marges",
  "figure": "le chiffre le plus fort du post, 10 caractères max, ex : 32 800 €, 24 jours, J+15",
  "figure_label": "ce que signifie ce chiffre pour le lecteur, 80 caractères max",
  "title": "l'idée du post en une affirmation, 70 caractères max"
}
RÈGLES :
- Uniquement des chiffres présents dans le post, jamais un chiffre inventé
- Si le post n'a aucun chiffre, "figure" vaut ""
- Vouvoiement, zéro jargon technique, aucun tiret cadratin, aucun emoji
- Jamais "PME type"
- RETOURNE UNIQUEMENT LE JSON, sans backticks, sans texte autour"""
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": f"Post :\n\n{post_content}"}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])
        if not data.get("title"):
            return None
        return {k: str(data.get(k) or "").replace("—", "-").strip()
                for k in ("kicker", "figure", "figure_label", "title")}
    except Exception as e:
        logger.warning(f"Extraction visuel échouée : {e}")
        return None


def _fallback_content(post_content: str, theme: str) -> dict:
    """Sans LLM : la première phrase du post devient l'affirmation."""
    words = [w for w in post_content.replace("\n", " ").split() if not w.startswith("#")]
    text = " ".join(words)
    for sep in (".", "!", "?"):
        idx = text.find(sep)
        if 20 < idx < 110:
            text = text[: idx + 1]
            break
    else:
        text = text[:100]
    return {"kicker": _kicker_for_theme(theme), "figure": "", "figure_label": "", "title": text}


# ─── Rendu ───────────────────────────────────────────────────────────────────

def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, kind, start, minimum, max_w, max_lines):
    size = start
    while size > minimum and len(_wrap(draw, text, _font(kind, size), max_w)) > max_lines:
        size -= 2
    return size


def _block(draw, text, x, y, font, lead, fill, max_w, max_lines):
    for ln in _wrap(draw, text, font, max_w)[:max_lines]:
        draw.text((x, y), ln, font=font, fill=fill)
        y += lead
    return y


def generate_post_image(theme: str, post_content: str = "") -> bytes:
    """Génère le visuel 1080x1350 à partir du post validé. Retourne des octets PNG."""
    from PIL import Image, ImageDraw

    data = _extract_visual_content(post_content) if post_content else None
    if not data:
        data = _fallback_content(post_content or theme, theme)
    LAST_VISUAL.clear()
    LAST_VISUAL.update(data)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Portrait sur grand cercle bleu clair, en bas à droite
    text_w = W - 2 * M
    if AVATAR_PATH.exists():
        try:
            d.ellipse([W - 240 - 350, H - 300 - 350, W - 240 + 350, H - 300 + 350], fill=SECONDARY)
            av = Image.open(AVATAR_PATH).convert("RGBA")
            av = av.crop((0, 0, av.width, int(av.height * 0.58)))
            disp_h = 680
            av = av.resize((int(av.width * disp_h / av.height), disp_h), Image.LANCZOS)
            img.paste(av, (W - av.width - 12, H - disp_h), av)
            text_w = 540
        except Exception as e:
            logger.warning(f"Avatar non intégré : {e}")

    # En-tête
    d.text((M, 64), (data.get("kicker") or _kicker_for_theme(theme)).upper(),
           font=_font("semibold", 22), fill=PRIMARY)

    y = 130
    # Chiffre clé
    if data.get("figure"):
        size = _fit(d, data["figure"], "black", 210, 110, W - 2 * M, 1)
        f = _font("black", size)
        d.text((M - 6, y), data["figure"], font=f, fill=PRIMARY)
        y += int(size * 1.12)
        if data.get("figure_label"):
            y = _block(d, data["figure_label"], M, y, _font("medium", 32), 44, MUTED, W - 2 * M - 40, 3)
        y += 44
    else:
        y += 60

    # Affirmation
    size = _fit(d, data["title"], "black", 62 if data.get("figure") else 76, 40, text_w, 5)
    _block(d, data["title"], M, y, _font("black", size), int(size * 1.18), INK, text_w, 5)

    # Étiquette nom
    d.rounded_rectangle([M, H - 236, M + 440, H - 132], radius=20, fill=INK)
    d.text((M + 32, H - 214), BRAND_NAME, font=_font("bold", 30), fill=WHITE)
    d.text((M + 32, H - 172), "Pilotage financier et outils pour PME", font=_font("regular", 22), fill=ACCENT)
    d.text((M, H - 80), "Optifin Data", font=_font("semibold", 24), fill=PRIMARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    logger.info(f"Visuel généré ({buf.tell() // 1024} KB) | thème : {theme}")
    return buf.getvalue()
