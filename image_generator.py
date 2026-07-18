"""
image_generator.py
Génère des visuels LinkedIn avec Pillow — template graphique (palette Ocean Breeze).

Style : quote card 1200x630px
  - Fond navy #2F4858 avec dégradé vers #336699
  - Kicker selon le thème + accroche Poppins Bold avec mot-clé vert #9EE493
  - Sous-ligne Lato Light Italic
  - Avatar détouré en bas à droite (avatar.png à la racine du projet)

Le contenu du visuel (accroche, mot-clé, sous-ligne) est extrait du post
validé via Claude. Fallback heuristique si l'appel échoue.
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
    BRAND_NAME, BRAND_TAGLINE = "Votre Nom", "Automatisation & Data pour la finance"

BASE_DIR = Path(__file__).parent
FONTS_DIR = BASE_DIR / "fonts"
AVATAR_PATH = BASE_DIR / "avatar.png"

# ─── Palette Ocean Breeze ────────────────────────────────────────────────────
NAVY_DARK  = (47, 72, 88)      # 2F4858 — fond
BLUE       = (51, 102, 153)    # 336699 — accent
BLUE_LIGHT = (134, 187, 216)   # 86BBD8 — texte secondaire
GREEN      = (158, 228, 147)   # 9EE493 — highlight
GREEN_PALE = (218, 247, 220)   # DAF7DC
WHITE      = (255, 255, 255)

W, H = 1200, 630

# ─── Polices (projet d'abord, système en fallback) ───────────────────────────
_FONT_CANDIDATES = {
    "title": [
        FONTS_DIR / "Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    ],
    "kicker": [
        FONTS_DIR / "Poppins-Medium.ttf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    ],
    "subline": [
        FONTS_DIR / "Lato-LightItalic.ttf",
        "/usr/share/fonts/truetype/lato/Lato-LightItalic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    ],
    "footer": [
        FONTS_DIR / "Lato-Regular.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    ],
}


def _load_font(kind: str, size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(str(path), size)
        except (IOError, OSError):
            continue
    logger.warning(f"Police '{kind}' introuvable — police par défaut")
    return ImageFont.load_default()


# ─── Kicker selon le thème ───────────────────────────────────────────────────
def _kicker_for_theme(theme: str) -> str:
    if "Tech" in theme or "IA" in theme:
        return "AUTOMATISATION · DATA & IA"
    return "FINANCE & COMPTABILITÉ"


# ─── Extraction du contenu visuel via Claude ─────────────────────────────────

def _extract_visual_content(post_content: str) -> Optional[dict]:
    """
    Demande à Claude d'extraire l'accroche du visuel depuis le post.
    Retourne {"lines": [...], "highlight": "...", "subline": "..."} ou None.
    """
    try:
        from anthropic import Anthropic
        from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        system = """Tu extrais le contenu d'un visuel LinkedIn depuis un post.
Retourne un JSON strict :
{
  "lines": ["ligne 1", "ligne 2", "ligne 3"],
  "highlight": "mot ou chiffre clé",
  "subline": "phrase de contexte"
}
RÈGLES :
- "lines" : l'accroche du post reformulée en 2 ou 3 lignes courtes, 26 caractères MAX par ligne
- L'accroche doit être percutante : le chiffre ou le fait le plus fort du post
- "highlight" : LE mot ou chiffre le plus impactant, il doit apparaître tel quel dans une des lignes
- "subline" : 1 phrase courte de contexte ou bénéfice (55 caractères max)
- RETOURNE UNIQUEMENT LE JSON, sans backticks, sans texte autour"""

        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": f"Post :\n\n{post_content}"}],
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break
        data = json.loads(raw)
        if not data.get("lines"):
            return None
        return data
    except Exception as e:
        logger.warning(f"Extraction visuel échouée : {e}")
        return None


def _fallback_content(post_content: str) -> dict:
    """Fallback sans LLM : première phrase découpée en lignes de ~24 chars."""
    clean = post_content.replace("\n", " ").strip()
    words = [w for w in clean.split() if not w.startswith("#")]
    clean = " ".join(words)
    for sep in [".", "!", "?"]:
        idx = clean.find(sep)
        if 20 < idx < 90:
            clean = clean[: idx + 1]
            break
    else:
        clean = clean[:80]

    lines, current = [], []
    for w in clean.split():
        current.append(w)
        if len(" ".join(current)) > 24:
            lines.append(" ".join(current[:-1]))
            current = [current[-1]]
        if len(lines) == 3:
            break
    if current and len(lines) < 3:
        lines.append(" ".join(current))

    return {"lines": lines, "highlight": "", "subline": ""}


# ─── Rendu ───────────────────────────────────────────────────────────────────

def generate_post_image(theme: str, post_content: str = "") -> bytes:
    """
    Génère le visuel 1200x630 : template graphique, contenu extrait du post.
    Retourne bytes PNG.
    """
    from PIL import Image, ImageDraw

    data = _extract_visual_content(post_content) if post_content else None
    if not data:
        data = _fallback_content(post_content or theme)

    lines = [str(l) for l in data.get("lines", [])][:3]
    highlight = str(data.get("highlight", "") or "")
    subline = str(data.get("subline", "") or "")

    img = Image.new("RGB", (W, H), NAVY_DARK)
    d = ImageDraw.Draw(img)

    # Dégradé navy → blue
    for y in range(H):
        r = y / H * 0.25
        c = tuple(int(NAVY_DARK[i] + (BLUE[i] - NAVY_DARK[i]) * r) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    # Barre accent top + cercles déco
    d.rectangle([0, 0, W, 8], fill=GREEN)
    d.ellipse([W - 220, -120, W + 80, 180], outline=BLUE_LIGHT, width=3)
    d.ellipse([W - 160, -60, W + 20, 120], outline=BLUE, width=3)

    # Kicker
    kick_font = _load_font("kicker", 24)
    d.text((70, 72), _kicker_for_theme(theme), font=kick_font, fill=GREEN)
    d.rectangle([70, 112, 150, 115], fill=GREEN)

    # Titre — taille auto-ajustée à la ligne la plus longue
    size = 64
    max_width = W - 140
    title_font = _load_font("title", size)
    while size > 40 and any(d.textlength(l, font=title_font) > max_width for l in lines):
        size -= 4
        title_font = _load_font("title", size)

    line_h = int(size * 1.38)
    n = len(lines)
    y0 = 160 if n == 3 else 190

    for i, line in enumerate(lines):
        y = y0 + i * line_h
        if highlight and highlight in line:
            before, after = line.split(highlight, 1)
            x = 70
            if before:
                d.text((x, y), before, font=title_font, fill=WHITE)
                x += d.textlength(before, font=title_font)
            d.text((x, y), highlight, font=title_font, fill=GREEN)
            x += d.textlength(highlight, font=title_font)
            if after:
                d.text((x, y), after, font=title_font, fill=WHITE)
        else:
            d.text((70, y), line, font=title_font, fill=WHITE)

    # Sous-ligne
    if subline:
        sub_font = _load_font("subline", 32)
        d.text((70, y0 + n * line_h + 35), subline, font=sub_font, fill=BLUE_LIGHT)

    # Avatar bas-droite
    if AVATAR_PATH.exists():
        try:
            av = Image.open(AVATAR_PATH).convert("RGBA")
            av = av.crop((0, 0, av.width, int(av.height * 0.52)))
            ratio = 300 / av.height
            av = av.resize((int(av.width * ratio), 300), Image.LANCZOS)
            img.paste(av, (W - av.width - 40, H - av.height), av)
        except Exception as e:
            logger.warning(f"Avatar non intégré : {e}")

    # Footer branding
    brand_font = _load_font("kicker", 24)
    foot_font = _load_font("footer", 20)
    d.text((70, H - 85), BRAND_NAME, font=brand_font, fill=WHITE)
    d.text((70, H - 52), BRAND_TAGLINE, font=foot_font, fill=BLUE_LIGHT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    logger.info(f"Visuel généré ({buf.tell() // 1024} KB) | thème : {theme}")
    buf.seek(0)
    return buf.read()
