#!/usr/bin/env bash
# =============================================================================
# setup.sh — Installation LinkedIn Automation sur Oracle Cloud (Ubuntu 22.04)
# =============================================================================
# Usage :
#   chmod +x setup.sh && ./setup.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$HOME/linkedin_automation"
VENV_DIR="$HOME/linkedin_env"

echo ""
echo "============================================================"
echo "  🚀  LinkedIn Automation — Setup Oracle Cloud Ubuntu VM"
echo "============================================================"
echo ""

# ─── 1. Mise à jour système ──────────────────────────────────────────────────
echo "📦 Mise à jour du système..."
sudo apt update -y && sudo apt upgrade -y

# ─── 2. Python 3.11 ──────────────────────────────────────────────────────────
echo "🐍 Vérification Python 3.11..."
if ! command -v python3.11 &>/dev/null; then
    sudo apt install -y software-properties-common
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update -y
    sudo apt install -y python3.11 python3.11-venv python3.11-distutils
fi
sudo apt install -y python3-pip git curl wget

echo "   Python : $(python3.11 --version)"

# ─── 3. Dossier projet ───────────────────────────────────────────────────────
echo "📁 Préparation du dossier projet : $PROJECT_DIR"
mkdir -p "$PROJECT_DIR/cookies"
mkdir -p "$PROJECT_DIR/logs"

# ─── 4. Environnement virtuel ─────────────────────────────────────────────────
echo "🔧 Création de l'environnement virtuel Python..."
python3.11 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ─── 5. Dépendances Python ───────────────────────────────────────────────────
echo "📦 Installation des dépendances Python..."
pip install --upgrade pip --quiet
pip install -r "$PROJECT_DIR/requirements.txt" --quiet

# ─── 6. Playwright + Chromium ────────────────────────────────────────────────
echo "🎭 Installation Playwright et Chromium..."
pip install playwright --quiet
playwright install chromium
playwright install-deps chromium

# ─── 7. Fichier .env ─────────────────────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo "⚠️  Configure tes clés API dans .env :"
    echo "   nano $PROJECT_DIR/.env"
    echo ""
fi

# ─── 8. Service systemd ──────────────────────────────────────────────────────
echo "🔄 Configuration du service systemd (auto-start au reboot)..."

cat > /tmp/linkedin_bot.service << EOF
[Unit]
Description=LinkedIn Automation Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_DIR/bin/python main.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/linkedin_bot.service /etc/systemd/system/linkedin_bot.service
sudo systemctl daemon-reload
sudo systemctl enable linkedin_bot

# ─── Résumé ──────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  ✅  Installation terminée !"
echo "============================================================"
echo ""
echo "  ÉTAPES RESTANTES :"
echo ""
echo "  1️⃣  Configure tes clés API :"
echo "      nano $PROJECT_DIR/.env"
echo ""
echo "  2️⃣  Copie les cookies LinkedIn (depuis ta machine locale) :"
echo "      scp -r cookies/ ubuntu@<IP_SERVEUR>:$PROJECT_DIR/"
echo "      (lance d'abord : python login_linkedin.py sur ta machine)"
echo ""
echo "  3️⃣  Démarre le bot :"
echo "      sudo systemctl start linkedin_bot"
echo "      sudo systemctl status linkedin_bot"
echo ""
echo "  4️⃣  Voir les logs en temps réel :"
echo "      journalctl -u linkedin_bot -f"
echo "      # ou :"
echo "      tail -f $PROJECT_DIR/linkedin_bot.log"
echo ""
echo "  5️⃣  Tester manuellement (hors scheduler) :"
echo "      source $VENV_DIR/bin/activate"
echo "      cd $PROJECT_DIR && python main.py"
echo "      # Envoie /generate sur Telegram"
echo ""
echo "============================================================"
echo ""
