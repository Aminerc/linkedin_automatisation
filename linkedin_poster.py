"""
linkedin_poster.py
Publie des posts LinkedIn.

Auth :
  - Images + Posts : Bearer LINKEDIN_ACCESS_TOKEN (API officielle api.linkedin.com)
  - Person ID      : cookie Voyager /me (lecture seule, fallback si LINKEDIN_PERSON_ID absent)

Endpoints officiels :
  - POST https://api.linkedin.com/rest/images?action=initializeUpload  → urn:li:image:*
  - POST https://api.linkedin.com/rest/documents?action=initializeUpload
  - POST https://api.linkedin.com/rest/posts
"""

import json
import logging
import re
import random
import time
from pathlib import Path
from typing import Optional

import requests

from config import (
    LINKEDIN_ACCESS_TOKEN,
    LINKEDIN_COOKIES_FILE,
    LINKEDIN_PERSON_ID,
)

logger = logging.getLogger(__name__)

# ─── Endpoints ────────────────────────────────────────────────────────────────
_API_BASE      = "https://api.linkedin.com"
# Version de l'API LinkedIn (format AAAAMM). LinkedIn retire chaque version
# au bout d'environ 1 an : on prend automatiquement le mois d'il y a 2 mois.
# Forçable via LINKEDIN_API_VERSION dans le .env.
def _default_li_version() -> str:
    import datetime
    d = datetime.date.today().replace(day=1)
    for _ in range(2):
        d = (d - datetime.timedelta(days=1)).replace(day=1)
    return d.strftime("%Y%m")


_LI_VERSION    = __import__("os").getenv("LINKEDIN_API_VERSION") or _default_li_version()

IMAGES_ENDPOINT    = f"{_API_BASE}/rest/images?action=initializeUpload"
DOCUMENTS_ENDPOINT = f"{_API_BASE}/rest/documents?action=initializeUpload"
POSTS_ENDPOINT     = f"{_API_BASE}/rest/posts"

# Pour person_id uniquement (cookie auth, lecture seule)
_ME_ENDPOINT = "https://www.linkedin.com/voyager/api/me"

# Fallback texte seul si pas de token OAuth
_NORM_SHARES = "https://www.linkedin.com/voyager/api/contentcreation/normShares"


# ─── Headers ──────────────────────────────────────────────────────────────────

def _api_headers() -> dict:
    """Headers API officielle LinkedIn (Bearer token)."""
    return {
        "Authorization":            f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Linkedin-Version":         _LI_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type":             "application/json",
    }


def _voyager_headers(cookies: dict) -> dict:
    """Headers Voyager (cookie auth) — utilisé uniquement pour /me."""
    csrf = cookies.get("JSESSIONID", "").strip('"')
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept":                  "application/vnd.linkedin.normalized+json+2.1",
        "X-RestLi-Protocol-Version": "2.0.0",
        "csrf-token":              csrf,
        "Origin":                  "https://www.linkedin.com",
        "Referer":                 "https://www.linkedin.com/feed/",
    }


# ─── Cookies ──────────────────────────────────────────────────────────────────

def _load_cookies() -> dict:
    if not LINKEDIN_COOKIES_FILE.exists():
        return {}
    with open(LINKEDIN_COOKIES_FILE, "r", encoding="utf-8") as f:
        return {c["name"]: c["value"] for c in json.load(f)}


# ─── Person ID ────────────────────────────────────────────────────────────────

def _get_person_id() -> Optional[str]:
    """Retourne le person_id depuis .env ou via l'API Voyager /me."""
    if LINKEDIN_PERSON_ID:
        return LINKEDIN_PERSON_ID

    cookies = _load_cookies()
    if not cookies:
        logger.warning("Pas de cookies — person_id introuvable")
        return None

    try:
        headers = _voyager_headers(cookies)
        r = requests.get(_ME_ENDPOINT, headers=headers, cookies=cookies, timeout=15)
        if r.status_code != 200:
            logger.warning(f"get_person_id → {r.status_code}")
            return None
        data = r.json()
        for key in ["plainId", "id", "memberId"]:
            v = data.get(key) or data.get("data", {}).get(key)
            if v:
                logger.info(f"Person ID ({key}) : {v}")
                return str(v)
        for item in data.get("included", []):
            for key in ["plainId", "memberId"]:
                v = item.get(key)
                if v and str(v).isdigit():
                    return str(v)
        logger.warning("person_id introuvable dans /me")
        return None
    except Exception as e:
        logger.warning(f"get_person_id error : {e}")
        return None


# ─── Upload binaire générique ─────────────────────────────────────────────────

def _put_binary(upload_url: str, data: bytes, content_type: str) -> bool:
    """PUT les bytes sur l'URL CDN pré-signée (pas de Authorization)."""
    r = requests.put(
        upload_url,
        headers={"Content-Type": content_type},
        data=data,
        timeout=120,
    )
    logger.info(f"PUT binary → {r.status_code}")
    if r.status_code not in [200, 201]:
        logger.error(f"PUT binary échoué ({r.status_code}): {r.text[:200]}")
        return False
    return True


# ─── Upload image ─────────────────────────────────────────────────────────────

def _initialize_image_upload(person_id: str) -> Optional[dict]:
    """
    POST /rest/images?action=initializeUpload
    Retourne dict {imageUrn, uploadUrl} ou None.
    """
    resp = requests.post(
        IMAGES_ENDPOINT,
        headers=_api_headers(),
        json={"initializeUploadRequest": {"owner": f"urn:li:person:{person_id}"}},
        timeout=20,
    )
    logger.info(f"initializeUpload image → {resp.status_code}")

    if resp.status_code not in [200, 201]:
        logger.error(f"initializeUpload image échoué [{resp.status_code}] : {resp.text[:400]}")
        return None

    value      = resp.json().get("value", {})
    image_urn  = value.get("image")
    upload_url = value.get("uploadUrl")

    if not image_urn or not upload_url:
        logger.error(f"initializeUpload image : champs manquants — {value}")
        return None

    if not image_urn.startswith("urn:li:image:"):
        logger.error(f"URN invalide (attendu urn:li:image:*) : {image_urn}")
        return None

    logger.info(f"Image initialisée → {image_urn}")
    return {"imageUrn": image_urn, "uploadUrl": upload_url}


def upload_image(person_id: str, image_bytes: bytes) -> Optional[str]:
    """
    Upload complet d'une image PNG.
    Retourne urn:li:image:* ou None.
    """
    info = _initialize_image_upload(person_id)
    if not info:
        return None
    if not _put_binary(info["uploadUrl"], image_bytes, "image/png"):
        return None
    logger.info(f"Image uploadée → {info['imageUrn']}")
    return info["imageUrn"]


# ─── Upload document (carousel PDF) ──────────────────────────────────────────

def _initialize_document_upload(person_id: str) -> Optional[dict]:
    """
    POST /rest/documents?action=initializeUpload
    Retourne dict {documentUrn, uploadUrl} ou None.
    """
    resp = requests.post(
        DOCUMENTS_ENDPOINT,
        headers=_api_headers(),
        json={"initializeUploadRequest": {"owner": f"urn:li:person:{person_id}"}},
        timeout=20,
    )
    logger.info(f"initializeUpload document → {resp.status_code}")

    if resp.status_code not in [200, 201]:
        logger.error(f"initializeUpload document échoué [{resp.status_code}] : {resp.text[:400]}")
        return None

    value      = resp.json().get("value", {})
    doc_urn    = value.get("document")
    upload_url = value.get("uploadUrl")

    if not doc_urn or not upload_url:
        logger.error(f"initializeUpload document : champs manquants — {value}")
        return None

    logger.info(f"Document initialisé → {doc_urn}")
    return {"documentUrn": doc_urn, "uploadUrl": upload_url}


def upload_document(person_id: str, pdf_bytes: bytes) -> Optional[str]:
    """
    Upload complet d'un PDF.
    Retourne urn:li:document:* ou None.
    """
    info = _initialize_document_upload(person_id)
    if not info:
        return None
    if not _put_binary(info["uploadUrl"], pdf_bytes, "application/pdf"):
        return None
    logger.info(f"Document uploadé → {info['documentUrn']}")
    return info["documentUrn"]


# ─── Payload builders ─────────────────────────────────────────────────────────

# Caractères réservés du format "little text" de LinkedIn : non échappés, ils
# tronquent ou abîment le post (ex : texte coupé à la première parenthèse).
_LITTLE_RESERVED = "\\|{}@[]()<>#*_~"


def _escape_little(text: str) -> str:
    """Échappe le texte pour le champ commentary et garde les hashtags cliquables."""
    text = text.replace("\r\n", "\n").replace("\u2028", "\n")
    out = "".join("\\" + ch if ch in _LITTLE_RESERVED else ch for ch in text)
    # \#Mot → {hashtag|\#|Mot} (hashtag cliquable)
    return re.sub(r"\\#(\w+)", r"{hashtag|\\#|\1}", out)


def _base_payload(person_id: str, commentary: str) -> dict:
    return {
        "author":       f"urn:li:person:{person_id}",
        "commentary":   _escape_little(commentary),
        "visibility":   "PUBLIC",
        "distribution": {
            "feedDistribution":            "MAIN_FEED",
            "targetEntities":              [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState":          "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


# ─── Envoi du post ────────────────────────────────────────────────────────────

def _send_post(payload: dict, context: str = "text") -> dict:
    """POST /rest/posts avec le payload donné."""
    time.sleep(random.uniform(1.0, 2.0))
    r = requests.post(
        POSTS_ENDPOINT,
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )
    logger.info(f"[{context}] POST /rest/posts → {r.status_code}")

    if r.status_code in [200, 201]:
        return {"success": True, "message": "✅ Publié avec succès sur LinkedIn !"}

    body = r.text[:400] if r.text else "pas de détail"
    logger.error(f"[{context}] Erreur {r.status_code} | {body}")

    msgs = {
        401: "❌ Token LinkedIn expiré (401). Relance get_linkedin_token.py et mets à jour LINKEDIN_ACCESS_TOKEN dans le .env du serveur.",
        403: "❌ Permission refusée (403). Vérifie que le produit 'Share on LinkedIn' est activé dans ta Developer App.",
        422: f"❌ Payload invalide (422) : {body}",
        429: "❌ Rate limit (429). Réessaie dans 10-15 min.",
    }
    return {"success": False, "message": msgs.get(r.status_code, f"❌ Erreur {r.status_code} : {body}")}


# ─── Fallback texte seul (normShares, sans token OAuth) ──────────────────────

def _send_text_fallback(content: str) -> dict:
    """Publie du texte seul via normShares (cookie auth) si le token OAuth est absent."""
    cookies = _load_cookies()
    if not cookies or not cookies.get("li_at"):
        return {"success": False, "message": "❌ Pas de cookies LinkedIn valides."}
    headers = {
        **_voyager_headers(cookies),
        "Content-Type": "application/json",
    }
    payload = {
        "visibleToConnectionsOnly": False,
        "externalAudienceProviders": [],
        "commentaryV2": {"text": content, "inferredLocale": "fr_FR"},
        "origin": "FEED",
        "allowedCommentersScope": "ALL",
        "postState": "PUBLISHED",
    }
    time.sleep(random.uniform(1.0, 2.0))
    r = requests.post(_NORM_SHARES, headers=headers, cookies=cookies, json=payload, timeout=30)
    logger.info(f"normShares (fallback) → {r.status_code}")
    if r.status_code in [200, 201]:
        return {"success": True, "message": "✅ Publié (texte seul) sur LinkedIn !"}
    return {"success": False, "message": f"❌ normShares {r.status_code} : {r.text[:200]}"}


# ─── API publique ─────────────────────────────────────────────────────────────

async def post_to_linkedin(content: str, image_bytes: Optional[bytes] = None) -> dict:
    """
    Publie un post texte (+ image optionnelle) sur LinkedIn.

    Flux image :
        1. initializeUpload → urn:li:image:*
        2. PUT binary
        3. POST /rest/posts avec content.media.id = urn:li:image:*

    Si LINKEDIN_ACCESS_TOKEN absent → fallback texte seul via normShares.
    """
    try:
        if not LINKEDIN_ACCESS_TOKEN:
            logger.warning("LINKEDIN_ACCESS_TOKEN absent → fallback normShares texte seul")
            return _send_text_fallback(content)

        person_id = _get_person_id()
        if not person_id:
            return {
                "success": False,
                "message": (
                    "❌ Impossible de récupérer ton ID LinkedIn.\n"
                    "Ajoute LINKEDIN_PERSON_ID=<ton_id> dans le .env (voir README)."
                ),
            }

        payload = _base_payload(person_id, content)

        # ── Texte seul ────────────────────────────────────────────────────────
        if not image_bytes:
            logger.info("Post texte → POST /rest/posts")
            return _send_post(payload, context="text")

        # ── Texte + image ─────────────────────────────────────────────────────
        image_urn = upload_image(person_id, image_bytes)
        if not image_urn:
            logger.warning("Upload image échoué → fallback texte seul")
            return _send_post(payload, context="text_fallback")

        payload["content"] = {"media": {"id": image_urn, "altText": ""}}
        logger.info(f"Post image → POST /rest/posts | {image_urn}")
        return _send_post(payload, context="single_image")

    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ Timeout LinkedIn (30s)."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "❌ Connexion impossible."}
    except Exception as e:
        logger.exception(f"Erreur inattendue post_to_linkedin : {e}")
        return {"success": False, "message": f"❌ Erreur inattendue : {str(e)}"}


async def post_carousel_to_linkedin(content: str, pdf_bytes: bytes, title: str) -> dict:
    """
    Publie un carousel PDF sur LinkedIn via l'API officielle Documents.
    """
    try:
        if not LINKEDIN_ACCESS_TOKEN:
            return {"success": False, "message": "❌ LINKEDIN_ACCESS_TOKEN manquant dans le .env."}

        person_id = _get_person_id()
        if not person_id:
            return {"success": False, "message": "❌ person_id introuvable."}

        logger.info(f"Upload carousel PDF ({len(pdf_bytes) // 1024} KB)...")
        doc_urn = upload_document(person_id, pdf_bytes)
        if not doc_urn:
            return {"success": False, "message": "❌ Échec upload carousel PDF."}

        payload = _base_payload(person_id, content)
        payload["content"] = {"media": {"id": doc_urn, "title": title}}

        logger.info(f"Carousel → POST /rest/posts | {doc_urn}")
        return _send_post(payload, context="document")

    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ Timeout LinkedIn (30s)."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "❌ Connexion impossible."}
    except Exception as e:
        logger.exception(f"Erreur inattendue post_carousel : {e}")
        return {"success": False, "message": f"❌ Erreur inattendue : {str(e)}"}
