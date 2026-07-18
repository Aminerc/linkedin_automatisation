# LinkedIn Automation Bot 🤖

Bot d'automatisation LinkedIn piloté par **Telegram** : génération de posts par IA (Claude / Perplexity), visuels de marque automatiques, publication via l'**API officielle LinkedIn**, et planification hebdomadaire.

```
Telegram (validation humaine)
   │
   ├── Génération du texte ──── Claude API / Perplexity API
   ├── Génération du visuel ─── Pillow (image) / ReportLab (PDF, carrousel)
   └── Publication ──────────── LinkedIn REST API (OAuth 2.0)
```

Tout passe par Telegram : **rien n'est publié sans ta validation**.

---

## Fonctionnalités

- **`/new`** — flow complet guidé : type de post → thème → validation du texte → validation du visuel → publication
- **3 types de posts** : texte seul, texte + PDF 1 page (quote card), texte + carrousel PDF (3-4 slides)
- **Double validation** : le texte ET le visuel sont validés séparément ; modifier le texte régénère automatiquement le visuel (synchronisation)
- **Édition ciblée** : "remplace 15 par 13", "ton moins commercial" — le post est modifié sans être réécrit
- **Visuels de marque** : template automatique (palette, polices Poppins/Lato, avatar, branding) généré depuis le texte validé
- **Planification** : posts automatiques proposés sur Telegram 3x/semaine (lun/mer/ven)
- **Multi-provider IA** : répartition Claude/Perplexity configurable, avec fallback automatique

---

## Le bot Telegram en détail

### Commandes

| Commande | Description |
|---|---|
| `/new` | Flow complet : type → thème → texte → visuel → publication |
| `/generate` | Génération rapide d'un post (choix du thème) |
| `/brief <sujet>` | Post sur un sujet précis |
| `/carousel [sujet]` | Carrousel PDF direct |
| `/status` | Posts en attente de validation |
| `/chatid` | Affiche ton chat ID |

### Flow `/new`

```
/new
 └─ 1. Type :   [📝 Texte] [📄 Texte + PDF] [🎠 Texte + Carrousel]
 └─ 2. Thème :  [💼 Finance & Compta] [🤖 Outils, Data & IA]
 └─ 3. Texte généré  → [✅ Valider] [✏️ Modifier] [❌ Refuser]
 └─ 4. Visuel généré → [✅ Valider] [🔄 Régénérer] [❌ Refuser]
 └─ 5. Les deux validés → [🚀 Publier sur LinkedIn]
```

Règles :
- ❌ Refuser le texte OU le visuel annule tout le post
- ✏️ Modifier le texte invalide le visuel : il est régénéré depuis le nouveau texte après re-validation
- 🔄 Régénérer le visuel ne touche pas au texte validé
- Un seul brouillon actif à la fois

### Planification automatique

Le scheduler (APScheduler) propose des posts sur Telegram — qui restent soumis à ta validation :
- **Lundi & vendredi ~8h30** (±20 min aléatoires) : post texte + visuel
- **Mercredi 8h00** : carrousel PDF

---

## Installation

### 1. Prérequis

- Python 3.10+
- Un bot Telegram (créé via [@BotFather](https://t.me/BotFather))
- Une clé API [Anthropic](https://console.anthropic.com/) (et optionnellement [Perplexity](https://www.perplexity.ai/settings/api))
- Une app [LinkedIn Developer](https://developer.linkedin.com/)

### 2. Cloner et installer

```bash
git clone https://github.com/<toi>/linkedin-automation.git
cd linkedin-automation
pip install -r requirements.txt
cp .env.example .env
```

### 3. Configurer Telegram

1. Crée ton bot via @BotFather → copie le token dans `TELEGRAM_BOT_TOKEN`
2. Lance `python get_chat_id.py`, envoie un message à ton bot → copie le chat ID dans `TELEGRAM_CHAT_ID`

Le bot ne répond **qu'à ton chat ID** — personne d'autre ne peut l'utiliser.

### 4. Configurer l'app LinkedIn

1. Crée une app sur [developer.linkedin.com](https://developer.linkedin.com/)
2. Dans **Products**, ajoute :
   - **Share on LinkedIn** (publication, scope `w_member_social`)
   - **Sign In with LinkedIn using OpenID Connect** (scopes `openid`, `profile`)
3. Dans **Auth** → *Authorized redirect URLs*, ajoute : `http://localhost/callback`
4. Copie Client ID et Client Secret dans `.env` (`LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`)

### 5. Générer le token OAuth

```bash
python get_linkedin_token.py
```

Le navigateur s'ouvre → autorise l'app → copie l'URL de redirection (`http://localhost/callback?code=...`) dans le terminal. Le script affiche :
- `LINKEDIN_ACCESS_TOKEN=...` → à mettre dans `.env` (⚠️ expire ~60 jours)
- Vérifie que les **scopes accordés** incluent bien `w_member_social`

Récupère ensuite ton **person ID** (l'ID opaque, pas l'ID numérique) :

```bash
python -c "
import urllib.request, json, os
from dotenv import load_dotenv; load_dotenv()
req = urllib.request.Request('https://api.linkedin.com/v2/userinfo', headers={'Authorization': 'Bearer ' + os.getenv('LINKEDIN_ACCESS_TOKEN','')})
print(json.loads(urllib.request.urlopen(req).read()).get('sub'))
"
```

→ mets la valeur dans `LINKEDIN_PERSON_ID`.

### 6. Personnaliser

- **Branding des visuels** : `BRAND_NAME` et `BRAND_TAGLINE` dans `.env`
- **Avatar** : place un PNG détouré (fond transparent) nommé `avatar.png` à la racine — il apparaîtra sur les visuels. Sans ce fichier, les visuels sont générés sans avatar.
- **Prompts** : copie `prompts/theme_finance_compta.md` en `prompts/theme_finance_compta.local.md` et personnalise-le (idem pour `theme_tech_ia.md`). Les fichiers `.local.md` sont prioritaires et **non versionnés**.
- **Planning** : jours/heures dans `scheduler.py`
- **Thèmes et sujets** : `content_generator.py` (`FORCED_TOPICS`) et `carousel_generator.py` (`CAROUSEL_TOPICS`)

### 7. Lancer

```bash
python main.py
```

Envoie `/start` à ton bot sur Telegram. C'est parti.

---

## Déploiement serveur (systemd)

Le script `setup.sh` automatise l'installation sur un VPS Ubuntu (testé sur Oracle Cloud Free Tier) :

```bash
scp -r . user@<IP>:~/linkedin_automation/
ssh user@<IP>
cd ~/linkedin_automation && chmod +x setup.sh && ./setup.sh
nano .env    # configure tes clés
sudo systemctl start linkedin_bot
journalctl -u linkedin_bot -f
```

Sur les petites VM (1 GB RAM), `start_server.sh` active le swap avant de démarrer le service.

---

## Architecture des fichiers

```
├── main.py                  # Point d'entrée : Telegram + scheduler
├── telegram_bot.py          # Bot Telegram, flow /new, validations
├── content_generator.py     # Génération de texte (Claude/Perplexity)
├── image_generator.py       # Visuels PNG (Pillow) — quote cards
├── carousel_generator.py    # PDF 1 page + carrousels (ReportLab)
├── linkedin_poster.py       # Publication API officielle LinkedIn
├── scheduler.py             # Planification APScheduler
├── config.py                # Configuration centralisée (.env)
├── get_linkedin_token.py    # Génération du token OAuth LinkedIn
├── get_chat_id.py           # Utilitaire : trouver son chat ID Telegram
├── prompts/                 # System prompts par thème (+ .local.md perso)
└── fonts/                   # Poppins & Lato (SIL Open Font License)
```

## Publication LinkedIn — détails techniques

Le bot utilise l'**API REST officielle** (`api.linkedin.com/rest/`) avec :
- `POST /rest/images?action=initializeUpload` → upload d'image (`urn:li:image:*`)
- `POST /rest/documents?action=initializeUpload` → upload de PDF/carrousel (`urn:li:document:*`)
- `POST /rest/posts` → publication

Headers requis : `Authorization: Bearer <token>`, `Linkedin-Version: 202507`, `X-Restli-Protocol-Version: 2.0.0`.

⚠️ Le token OAuth expire environ tous les 60 jours — relance `get_linkedin_token.py` pour le renouveler.

---

## Sécurité

- `.env` (clés API, tokens) n'est **jamais** versionné
- Le bot Telegram est verrouillé sur un seul chat ID
- Les prompts personnalisés (`*.local.md`), l'avatar et les cookies sont exclus du repo

## Licence

Les polices Poppins et Lato sont distribuées sous [SIL Open Font License](https://scripts.sil.org/OFL).
