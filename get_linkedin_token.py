"""
get_linkedin_token.py
Génère un OAuth 2.0 access token LinkedIn (w_member_social).

Usage : python get_linkedin_token.py
"""

import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser

from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost/callback"
SCOPE         = "w_member_social openid profile"

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ LINKEDIN_CLIENT_ID et LINKEDIN_CLIENT_SECRET manquants dans .env")
    exit(1)

state = secrets.token_urlsafe(16)

auth_url = (
    "https://www.linkedin.com/oauth/v2/authorization"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPE)}"
    f"&state={state}"
    f"&prompt=consent"  # Force le ré-affichage du consentement pour obtenir w_member_social
)

print("🔗 Ouvre ce lien dans ton navigateur (sur ton PC si tu es sur le serveur) :")
print()
print(auth_url)
print()
try:
    webbrowser.open(auth_url)
except Exception:
    pass
print("\nAprès avoir cliqué 'Autoriser' sur LinkedIn,")
print("ton navigateur va afficher une erreur (page introuvable) — c'est normal.")
print("\nCopie l'URL complète de la barre d'adresse et colle-la ici :")
print()

callback_url = input("URL de redirection : ").strip()

parsed = urllib.parse.urlparse(callback_url)
params = urllib.parse.parse_qs(parsed.query)

if "error" in params:
    print(f"❌ Erreur LinkedIn : {params.get('error_description', ['inconnu'])[0]}")
    exit(1)

if "code" not in params:
    print("❌ Pas de code dans l'URL. Vérifie que tu as bien copié l'URL complète.")
    exit(1)

auth_code = params["code"][0]
print(f"\n✅ Code reçu, échange contre un token...")

token_data = urllib.parse.urlencode({
    "grant_type":    "authorization_code",
    "code":          auth_code,
    "redirect_uri":  REDIRECT_URI,
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
}).encode()

req = urllib.request.Request(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data=token_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)

try:
    with urllib.request.urlopen(req) as resp:
        token_resp = json.loads(resp.read())
except Exception as e:
    print(f"❌ Erreur échange token : {e}")
    exit(1)

access_token = token_resp.get("access_token")
expires_in   = token_resp.get("expires_in", 0)

if not access_token:
    print(f"❌ Pas de token : {token_resp}")
    exit(1)

scope = token_resp.get("scope", "NON RETOURNÉ")

print("\n" + "═" * 60)
print("✅ TOKEN OBTENU")
print("═" * 60)
print(f"Expire dans : {expires_in // 86400} jours")
print(f"Scopes accordés : {scope}\n")
print("Ajoute cette ligne dans le .env du SERVEUR :\n")
print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
print("\n" + "═" * 60)
