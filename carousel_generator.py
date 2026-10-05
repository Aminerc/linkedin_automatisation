"""
carousel_generator.py
Carrousels LinkedIn Optifin Data, style "note de pilotage, version humaine" (format 4:5).

Pages :
  1. Couverture : chiffre qui frappe, promesse, portrait d'Amine
  2. Constats (3) : phrase du dirigeant, constat, preuve chiffrée, "ce que je ferais à votre place"
  3. "Ce que ça donne" : zooms annotés d'un vrai tableau de bord de démonstration
  4. Diagnostic en 5 questions
  5. Fin signée : "Je m'appelle Amine", une seule action

Flow :
  generate_carousel_content()   → Claude génère le contenu structuré (JSON)
  generate_carousel_from_text() → idem, à partir d'un texte de post déjà validé
  create_carousel_pdf()         → reportlab crée le PDF
"""

import io
import json
import logging
import random
from pathlib import Path
from typing import Optional

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

logger = logging.getLogger(__name__)

try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME, BRAND_TAGLINE = "Amine Ouardi", "Pilotage financier et outils sur mesure pour les PME"

from dashboards import DASHBOARDS

BASE_DIR = Path(__file__).parent
FONTS_DIR = BASE_DIR / "fonts"
AVATAR = BASE_DIR / "avatar.png"
DASH_DIR = BASE_DIR / "assets" / "dashboards"

BRAND_LINE = f"{BRAND_NAME} · Optifin Data"

# ─── Sujets par thème ─────────────────────────────────────────────────────────
CAROUSEL_TOPICS = {
    "Finance, Compta & Gestion": [
        "Les signes que votre reporting vous coûte plus qu'il ne vous sert",
        "Pourquoi le chiffre d'affaires monte et la marge baisse",
        "Les retards de paiement clients qui pèsent sur la trésorerie",
        "Ce que coûte une clôture mensuelle trop lente",
        "Le stock qui dort et immobilise la trésorerie",
        "Les indicateurs financiers qu'un dirigeant devrait voir chaque mois",
        "Budget annuel : pourquoi il ne sert plus à rien en mars",
        "Les clients qui rapportent moins qu'ils ne coûtent",
    ],
    "Tech & IA appliquée à la Finance": [
        "Les tâches de reporting qui ne devraient plus être faites à la main",
        "Excel ou tableau de bord : quand il est temps de passer le cap",
        "Les relances clients qui peuvent partir toutes seules",
        "Ce que change un tableau de bord mis à jour chaque matin",
        "Les signes qu'une seule personne tient tout le pilotage",
        "Pourquoi deux personnes donnent deux chiffres différents",
    ],
}

# ─── Charte Ocean Breeze ──────────────────────────────────────────────────────
INK = colors.HexColor("#2F4858")
PRIMARY = colors.HexColor("#336699")
SECONDARY = colors.HexColor("#86BBD8")
ACCENT = colors.HexColor("#9EE493")
ACCENT_BG = colors.HexColor("#DAF7DC")
BG = colors.HexColor("#F5F7F9")
BORDER = colors.HexColor("#DDE4EA")
MUTED = colors.HexColor("#6B7B87")
NEG = colors.HexColor("#C0564F")
WHITE = colors.white

W, H = 540, 675   # 4:5 portrait
M = 40


# ═════════════════════════════════════════════════════════════════════════════
# Génération du contenu (Claude)
# ═════════════════════════════════════════════════════════════════════════════

def _dashboard_menu() -> str:
    return "\n".join(f'  "{k}" : {v["about"]}' for k, v in DASHBOARDS.items())


CAROUSEL_SPEC = """
═══ CONSIGNE SPÉCIFIQUE : CARROUSEL ═══
Ignore la consigne de format de sortie ci-dessus. Ici tu produis un carrousel LinkedIn en JSON.
Toutes les règles de voix, de crédibilité et de zéro jargon ci-dessus restent obligatoires.

Le carrousel doit apporter une valeur que le texte du post n'apporte pas : chaque constat montre
une preuve chiffrée et donne un réflexe concret applicable dès ce mois-ci.

Retourne un JSON strict, exactement ces clés :
{{
  "kicker": "2 à 3 mots, ex : Pilotage · Reporting",
  "hook_figure": "le chiffre qui frappe, 10 caractères max, ex : 24 jours, 351 k€, J+15",
  "hook_figure_label": "ce que signifie ce chiffre pour le lecteur, au conditionnel ou à la 2e personne, 90 caractères max. Ex : par an, si votre reporting vous prend 2 jours chaque mois.",
  "title": "la promesse du carrousel, 70 caractères max",
  "intro": "le texte du post LinkedIn qui accompagne le carrousel : 120 à 200 mots, hook en ligne 1, paragraphes de 1 à 3 lignes séparés par une ligne vide, une seule clôture : appel à écrire en message privé, 2 à 3 hashtags sur la dernière ligne",
  "slides": [
    {{
      "quote": "une phrase qu'un dirigeant de PME dit vraiment, à la 1re personne, 80 caractères max, sans guillemets",
      "title": "le constat, formulé comme une affirmation, 60 caractères max",
      "exhibit": UNE des deux formes ci-dessous,
      "action": "ce que je ferais à votre place : à la 1re personne (Amine), concret, applicable ce mois-ci, 140 caractères max, commence par Je"
    }}
  ],
  "checklist_title": "ex : Votre reporting en 5 questions",
  "checklist": ["5 situations courtes à cocher, 55 caractères max chacune, formulées comme des constats"],
  "score_rule": "ex : Deux cases ou plus : votre reporting vous coûte déjà. (65 caractères max)",
  "signoff": "2 phrases à la 1re personne : ce que tu fais pour les dirigeants, puis une invitation précise liée au diagnostic. 230 caractères max",
  "dashboard": "la clé du tableau de bord de démonstration le plus proche du sujet, ou null"
}}

Formes possibles de "exhibit" :
  Comparaison (2 valeurs qui devraient être égales ou proches) :
    {{"type": "compare", "items": [{{"label": "Marge de mars, fichier comptable", "value": "31,2 %"}},
                                  {{"label": "Marge de mars, fichier commercial", "value": "34,8 %"}}],
     "gap": "3,6 points d'écart pour le même mois"}}
  Barres (3 à 5 lignes, la ligne qui pose problème en "highlight") :
    {{"type": "bars", "rows": [{{"label": "Recoller les exports", "value": 9, "display": "9 h", "highlight": true}},
                               {{"label": "Analyser et décider", "value": 1, "display": "1 h"}}],
     "note": "Heures passées chaque mois sur un reporting de 2 jours"}}

Règles du carrousel :
- 3 slides exactement dans "slides", chacune avec une forme de preuve adaptée (varie les formes).
- Les chiffres des preuves sont des ordres de grandeur réalistes qui illustrent une situation courante.
  Les libellés restent génériques ("fichier comptable", "Recoller les exports") : jamais un nom
  d'entreprise, jamais "un client", jamais "PME type", jamais "exemple fictif".
- "value" dans les barres : un nombre. "display" : ce nombre avec son unité.
- Libellés de barres : 22 caractères max.
- Aucun tiret cadratin, aucun emoji, aucun mot technique (data warehouse, SQL, API, ETL...).

Tableaux de bord de démonstration disponibles pour "dashboard" :
{menu}

RETOURNE UNIQUEMENT LE JSON, sans backticks, sans texte autour.
"""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def _clean(text, max_len: Optional[int] = None) -> str:
    s = str(text or "").replace("—", "-").replace("–", "-").strip()
    if max_len and len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def _sanitize(data: dict) -> dict:
    """Rend la sortie de Claude sûre pour la mise en page (longueurs, types, preuves valides)."""
    out = {
        "kicker": _clean(data.get("kicker"), 32) or "Pilotage",
        "hook_figure": _clean(data.get("hook_figure"), 12),
        "hook_figure_label": _clean(data.get("hook_figure_label"), 110),
        "title": _clean(data.get("title"), 90),
        "intro": str(data.get("intro", "")).replace("—", "-").strip(),
        "checklist_title": _clean(data.get("checklist_title"), 50) or "Le diagnostic en 5 questions",
        "checklist": [_clean(x, 70) for x in (data.get("checklist") or [])][:5],
        "score_rule": _clean(data.get("score_rule"), 75),
        "signoff": _clean(data.get("signoff"), 260),
        "dashboard": data.get("dashboard") if data.get("dashboard") in DASHBOARDS else None,
        "slides": [],
    }
    for i, s in enumerate((data.get("slides") or [])[:4]):
        slide = {
            "number": f"{i + 1:02d}",
            "quote": _clean(s.get("quote"), 95).strip("«»\" "),
            "title": _clean(s.get("title"), 75),
            "action": _clean(s.get("action"), 170),
            "exhibit": None,
        }
        ex = s.get("exhibit") or {}
        try:
            if ex.get("type") == "compare" and 2 <= len(ex.get("items", [])) <= 3:
                slide["exhibit"] = {
                    "type": "compare",
                    "items": [{"label": _clean(it["label"], 45), "value": _clean(it["value"], 10)}
                              for it in ex["items"]],
                    "gap": _clean(ex.get("gap"), 60),
                }
            elif ex.get("type") == "bars" and 2 <= len(ex.get("rows", [])) <= 5:
                rows = [{"label": _clean(r["label"], 24), "value": float(r["value"]),
                         "display": _clean(r.get("display", r["value"]), 10),
                         "highlight": bool(r.get("highlight"))} for r in ex["rows"]]
                if max(r["value"] for r in rows) > 0:
                    slide["exhibit"] = {"type": "bars", "rows": rows, "note": _clean(ex.get("note"), 70)}
        except (KeyError, TypeError, ValueError):
            slide["exhibit"] = None
        out["slides"].append(slide)
    # Champs attendus par le bot Telegram
    out["subtitle"] = f'{out["hook_figure"]} {out["hook_figure_label"]}'.strip()
    return out


def _call_claude(system: str, user_msg: str) -> dict:
    from anthropic import Anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")
    return _sanitize(_extract_json(raw))


def _system_prompt(theme: str) -> str:
    from content_generator import load_prompt
    return load_prompt(theme) + "\n\n" + CAROUSEL_SPEC.format(menu=_dashboard_menu())


def generate_carousel_content(theme: Optional[str] = None, custom_brief: Optional[str] = None) -> dict:
    """Génère un carrousel complet sur un sujet (tiré au sort ou fourni)."""
    from content_generator import THEMES

    if not theme:
        theme = random.choice(list(THEMES.keys()))
    subject = custom_brief or random.choice(CAROUSEL_TOPICS.get(theme, CAROUSEL_TOPICS["Finance, Compta & Gestion"]))

    logger.info(f"Génération carousel | sujet : {subject} | thème : {theme}")
    data = _call_claude(_system_prompt(theme), f"Crée le carrousel sur ce sujet : {subject}")
    data["subject"] = subject
    data["theme"] = theme
    return data


def generate_carousel_from_text(post_text: str, theme: str) -> dict:
    """Génère un carrousel à partir d'un texte de post DÉJÀ validé (le texte du post est conservé)."""
    logger.info(f"Génération carousel depuis texte | thème : {theme}")
    user_msg = (
        "Voici le texte final d'un post LinkedIn, déjà validé. Construis le carrousel qui l'accompagne : "
        "mêmes idées, mêmes chiffres quand ils existent, et une valeur en plus (preuves, réflexes, diagnostic). "
        "Le champ intro peut rester vide, le texte du post est conservé tel quel.\n\n"
        f"{post_text}"
    )
    data = _call_claude(_system_prompt(theme), user_msg)
    data["intro"] = post_text
    data["subject"] = data.get("title", "")
    data["theme"] = theme
    return data


# ═════════════════════════════════════════════════════════════════════════════
# Mise en page PDF
# ═════════════════════════════════════════════════════════════════════════════

def _fonts() -> dict:
    out = {}
    for key, name, fallback in [("r", "Inter-Regular", "Helvetica"), ("m", "Inter-Medium", "Helvetica"),
                                ("s", "Inter-SemiBold", "Helvetica-Bold"), ("b", "Inter-Bold", "Helvetica-Bold"),
                                ("x", "Inter-ExtraBold", "Helvetica-Bold"),
                                ("q", "Inter-MediumItalic", "Helvetica-Oblique")]:
        try:
            pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / f"{name}.ttf")))
            out[key] = name
        except Exception:
            out[key] = fallback
    return out


def _wrap(c, text, font, size, max_w):
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _block(c, text, x, y, font, size, lead, color, max_w, max_lines=None):
    lines = _wrap(c, text, font, size, max_w)
    if max_lines:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    for ln in lines:
        c.drawString(x, y, ln)
        y -= lead
    return y


def _fit(c, text, font, start, minimum, max_w, max_lines):
    s = start
    while s > minimum and len(_wrap(c, text, font, s, max_w)) > max_lines:
        s -= 1
    return s


def _page(c, color):
    c.setFillColor(color)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def _header(c, f, left, right, dark=False):
    c.setFont(f["s"], 10)
    c.setFillColor(ACCENT if dark else PRIMARY)
    c.drawString(M, H - 40, left.upper())
    c.setFont(f["m"], 10)
    c.setFillColor(SECONDARY if dark else MUTED)
    c.drawRightString(W - M, H - 40, right)


def _footer(c, f, hint="→"):
    c.setFont(f["s"], 10)
    c.setFillColor(INK)
    c.drawString(M, 30, BRAND_LINE)
    if hint:
        c.setFont(f["s"], 11)
        c.setFillColor(PRIMARY)
        c.drawRightString(W - M, 30, hint)


def _portrait():
    if AVATAR.exists():
        try:
            im = Image.open(AVATAR).convert("RGBA")
            im.thumbnail((640, 1400))  # suffisant pour l'affichage, garde un PDF léger
            return im
        except Exception:
            pass
    return None


def _round_avatar(c, portrait, x, y, d):
    w, h = portrait.size
    head = portrait.crop((int(w * 0.18), 0, int(w * 0.82), int(w * 0.64)))
    head = head.resize((160, 160))
    bg = Image.new("RGBA", head.size, (218, 247, 220, 255))
    bg.alpha_composite(head)
    c.saveState()
    p = c.beginPath()
    p.circle(x + d / 2, y + d / 2, d / 2)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(ImageReader(bg.convert("RGB")), x, y, width=d, height=d)
    c.restoreState()


def _ex_compare(c, f, ex, top):
    items = ex["items"]
    cw = (W - 2 * M) / len(items)
    for i, it in enumerate(items):
        x = M + i * cw
        _block(c, it["label"], x, top - 4, f["m"], 12, 15, MUTED, cw - 20, 2)
        vs = _fit(c, it["value"], f["x"], 46, 26, cw - 20, 1)
        c.setFont(f["x"], vs)
        c.setFillColor(PRIMARY)
        c.drawString(x, top - 40 - vs * 0.75, it["value"])
        if i:
            c.setStrokeColor(BORDER)
            c.setLineWidth(1)
            c.line(x - 12, top + 4, x - 12, top - 100)
    y = top - 120
    if ex.get("gap"):
        y = _block(c, ex["gap"], M, y, f["b"], 15, 19, NEG, W - 2 * M, 2) - 4
    return y


def _ex_bars(c, f, ex, top):
    rows = ex["rows"]
    vmax = max(r["value"] for r in rows)
    label_w = 165
    bar_x = M + label_w
    bar_wmax = W - 2 * M - label_w - 55
    y = top - 6
    for r in rows:
        hi = r.get("highlight")
        c.setFont(f["s"] if hi else f["m"], 13)
        c.setFillColor(INK)
        c.drawString(M, y - 4, r["label"])
        bw = max(4, bar_wmax * r["value"] / vmax)
        c.setFillColor(NEG if hi else SECONDARY)
        c.roundRect(bar_x, y - 9, bw, 20, 4, fill=1, stroke=0)
        c.setFont(f["b"], 13)
        c.setFillColor(NEG if hi else INK)
        c.drawString(bar_x + bw + 8, y - 4, r["display"])
        y -= 38
    if ex.get("note"):
        c.setFont(f["r"], 11)
        c.setFillColor(MUTED)
        c.drawString(M, y + 6, ex["note"])
        y -= 14
    return y


EXHIBITS = {"compare": _ex_compare, "bars": _ex_bars}


def create_carousel_pdf(data: dict) -> bytes:
    f = _fonts()
    portrait = _portrait()
    slides = data.get("slides", [])
    dash = DASHBOARDS.get(data.get("dashboard") or "")
    if dash and not (DASH_DIR / dash["image"]).exists():
        dash = None
    n_pages = 3 + len(slides) + (1 if dash else 0)
    p = 1

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(data.get("title", "Carrousel"))
    c.setAuthor(BRAND_LINE)

    # ── 1. Couverture ────────────────────────────────────────────────────────
    _page(c, BG)
    text_w = W - 2 * M
    if portrait:
        c.setFillColor(SECONDARY)
        c.circle(W - 120, 150, 175, fill=1, stroke=0)
        pw, ph = portrait.size
        upper = portrait.crop((0, 0, pw, int(ph * 0.58)))
        disp_h = 340
        disp_w = disp_h * upper.size[0] / upper.size[1]
        c.drawImage(ImageReader(upper), W - disp_w - 6, 0, width=disp_w, height=disp_h, mask="auto")
        text_w = 262
    _header(c, f, data.get("kicker", ""), f"{p} / {n_pages}")
    y = H - 90
    if data.get("hook_figure"):
        hs = _fit(c, data["hook_figure"], f["x"], 104, 56, W - 2 * M, 1)
        base = y - hs * 0.75
        c.setFont(f["x"], hs)
        c.setFillColor(PRIMARY)
        c.drawString(M - 4, base, data["hook_figure"])
        y = base - hs * 0.28 - 18
        y = _block(c, data.get("hook_figure_label", ""), M, y, f["m"], 16, 22, MUTED, W - 2 * M - 20, 3) - 22
    ts = _fit(c, data.get("title", ""), f["x"], 30, 20, text_w, 5)
    _block(c, data.get("title", ""), M, y, f["x"], ts, ts * 1.18, INK, text_w, 5)
    c.setFillColor(INK)
    c.roundRect(M, 64, 214, 52, 10, fill=1, stroke=0)
    c.setFont(f["b"], 14)
    c.setFillColor(WHITE)
    c.drawString(M + 16, 94, BRAND_NAME)
    c.setFont(f["r"], 10.5)
    c.setFillColor(ACCENT)
    c.drawString(M + 16, 76, "Pilotage financier et outils pour PME")
    c.setFont(f["s"], 11)
    c.setFillColor(PRIMARY)
    c.drawString(M, 30, "Faites défiler  →")
    c.showPage()
    p += 1

    # ── 2. Constats ──────────────────────────────────────────────────────────
    for i, s in enumerate(slides):
        _page(c, WHITE)
        _header(c, f, f"Constat {i + 1}", f"{p} / {n_pages}")
        y = H - 132
        if s.get("quote"):
            c.setFont(f["x"], 64)
            c.setFillColor(ACCENT)
            c.drawString(M - 4, H - 116, "«")
            qs = _fit(c, s["quote"], f["q"], 24, 17, W - 2 * M, 3)
            y = _block(c, s["quote"], M, y, f["q"], qs, qs * 1.3, INK, W - 2 * M, 3)
            c.setFont(f["r"], 12)
            c.setFillColor(MUTED)
            c.drawString(M, y - 4, "Ce que j'entends souvent chez les dirigeants")
            y -= 34
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.line(M, y, W - M, y)
        y -= 26
        y = _block(c, s.get("title", ""), M, y, f["b"], 18, 23, INK, W - 2 * M, 2) - 14
        if s.get("exhibit"):
            y = EXHIBITS[s["exhibit"]["type"]](c, f, s["exhibit"], y)

        if s.get("action"):
            lines = _wrap(c, s["action"], f["m"], 14, W - 2 * M - 92)[:4]
            box_h = max(92, 50 + 20 * len(lines))
            c.setFillColor(ACCENT_BG)
            c.roundRect(M, 70, W - 2 * M, box_h, 12, fill=1, stroke=0)
            tx = M + 18
            if portrait:
                _round_avatar(c, portrait, M + 16, 70 + box_h - 62, 48)
                tx = M + 78
            c.setFont(f["b"], 11)
            c.setFillColor(INK)
            c.drawString(tx, 70 + box_h - 26, "CE QUE JE FERAIS À VOTRE PLACE")
            ty = 70 + box_h - 48
            c.setFont(f["m"], 14)
            for ln in lines:
                c.drawString(tx, ty, ln)
                ty -= 20
        _footer(c, f)
        c.showPage()
        p += 1

    # ── 3. Ce que ça donne : vrai tableau de bord ────────────────────────────
    if dash:
        _page(c, BG)
        _header(c, f, "Ce que ça donne", f"{p} / {n_pages}")
        y = _block(c, "Le même sujet, sur une seule page", M, H - 88, f["b"], 24, 30, INK, W - 2 * M, 2)
        y = _block(c, f"{dash['name']} : un de mes tableaux de bord de démonstration, construit dans Power BI.",
                   M, y - 2, f["r"], 13, 18, MUTED, W - 2 * M, 2) - 12
        src = Image.open(DASH_DIR / dash["image"]).convert("RGB")
        sw0, sh0 = src.size
        notes_h = 30 * len(dash["notes"]) + 40
        pin_no = 0
        for shot_def in dash["shots"]:
            l, t, r_, b_ = shot_def["crop"]
            shot = src.crop((int(l * sw0), int(t * sh0), int(r_ * sw0), int(b_ * sh0)))
            sw, sh = shot.size
            img_w = W - 2 * M
            img_h = img_w * sh / sw
            avail = y - 60 - notes_h
            if img_h > avail:  # graphique trop haut : on réduit en gardant les proportions
                img_h = max(avail, 80)
                img_w = img_h * sw / sh
            x0 = M + (W - 2 * M - img_w) / 2
            img_y = y - img_h
            c.setFillColor(WHITE)
            c.setStrokeColor(BORDER)
            c.roundRect(x0 - 6, img_y - 6, img_w + 12, img_h + 12, 10, fill=1, stroke=1)
            c.drawImage(ImageReader(shot), x0, img_y, width=img_w, height=img_h)
            for (rx, ry) in shot_def.get("pins", []):
                pin_no += 1
                cx, cy = x0 + rx * img_w, img_y + (1 - ry) * img_h
                c.setFillColor(INK)
                c.circle(cx, cy, 12, fill=1, stroke=0)
                c.setFont(f["b"], 12)
                c.setFillColor(ACCENT)
                c.drawCentredString(cx, cy - 4, str(pin_no))
            y = img_y - 22
        y -= 6
        for k, note in enumerate(dash["notes"][:pin_no]):
            c.setFillColor(INK)
            c.circle(M + 11, y + 4, 11, fill=1, stroke=0)
            c.setFont(f["b"], 11)
            c.setFillColor(ACCENT)
            c.drawCentredString(M + 11, y, str(k + 1))
            y = _block(c, note, M + 32, y, f["m"], 14, 19, INK, W - 2 * M - 32, 2) - 10
        _footer(c, f)
        c.showPage()
        p += 1

    # ── 4. Diagnostic ────────────────────────────────────────────────────────
    _page(c, WHITE)
    _header(c, f, "Diagnostic en 2 minutes", f"{p} / {n_pages}")
    y = _block(c, data.get("checklist_title", ""), M, H - 88, f["b"], 26, 31, INK, W - 2 * M, 2)
    y = _block(c, "Cochez ce qui vous ressemble, sur le mois dernier.", M, y - 2,
               f["r"], 14, 19, MUTED, W - 2 * M, 2) - 18
    for item in data.get("checklist", []):
        c.setStrokeColor(PRIMARY)
        c.setLineWidth(1.8)
        c.roundRect(M, y - 13, 20, 20, 5, fill=0, stroke=1)
        ty = y - 2
        c.setFont(f["m"], 15)
        c.setFillColor(INK)
        for ln in _wrap(c, item, f["m"], 15, W - 2 * M - 44)[:2]:
            c.drawString(M + 36, ty, ln)
            ty -= 20
        y = ty - 20
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.line(M, y + 12, W - M, y + 12)
    if data.get("score_rule"):
        y -= 8
        lines = _wrap(c, data["score_rule"], f["b"], 15, W - 2 * M - 36)[:2]
        bh = 30 + 20 * len(lines)
        c.setFillColor(ACCENT_BG)
        c.roundRect(M, y - bh + 6, W - 2 * M, bh, 12, fill=1, stroke=0)
        ty = y - 18
        c.setFont(f["b"], 15)
        c.setFillColor(INK)
        for ln in lines:
            c.drawString(M + 18, ty, ln)
            ty -= 20
    _footer(c, f, hint="Enregistrez pour refaire le test")
    c.showPage()
    p += 1

    # ── 5. Fin signée ────────────────────────────────────────────────────────
    _page(c, INK)
    if portrait:
        c.setFillColor(PRIMARY)
        c.circle(W - 120, 120, 190, fill=1, stroke=0)
        pw, ph = portrait.size
        upper = portrait.crop((0, 0, pw, int(ph * 0.62)))
        disp_h = 360
        disp_w = disp_h * upper.size[0] / upper.size[1]
        c.drawImage(ImageReader(upper), W - disp_w + 10, 0, width=disp_w, height=disp_h, mask="auto")
    _header(c, f, "Et maintenant", f"{p} / {n_pages}", dark=True)
    y = _block(c, f"Je m'appelle {BRAND_NAME.split()[0]}.", M, H - 110, f["x"], 30, 36, WHITE, W - 2 * M, 2)
    y = _block(c, data.get("signoff", ""), M, y - 12, f["r"], 16, 23, SECONDARY, W - 2 * M - 10, 6)
    c.setFillColor(ACCENT)
    c.roundRect(M, y - 64, 270, 50, 10, fill=1, stroke=0)
    c.setFont(f["b"], 15)
    c.setFillColor(INK)
    c.drawCentredString(M + 135, y - 44, "Écrivez-moi en message privé")
    c.setFont(f["b"], 13)
    c.setFillColor(WHITE)
    c.drawString(M, y - 96, BRAND_LINE)
    _block(c, BRAND_TAGLINE, M, y - 114, f["r"], 10.5, 14, SECONDARY, 220, 2)
    c.showPage()

    c.save()
    logger.info(f"Carrousel PDF généré : {n_pages} pages ({buf.tell() // 1024} KB)")
    return buf.getvalue()


# ─── PDF 1 page (quote card) : inchangé ──────────────────────────────────────

def create_quote_pdf(theme: str, post_text: str) -> bytes:
    """Crée un PDF 1 page à partir de la quote card PNG (image_generator)."""
    from image_generator import generate_post_image

    png_bytes = generate_post_image(theme, post_text)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(1200, 630))
    c.drawImage(ImageReader(io.BytesIO(png_bytes)), 0, 0, width=1200, height=630)
    c.showPage()
    c.save()
    logger.info(f"Quote PDF généré ({buf.tell() // 1024} KB)")
    return buf.getvalue()
