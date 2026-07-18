"""
get_chat_id.py
Script utilitaire pour trouver ton TELEGRAM_CHAT_ID.

Usage :
  1. Mets ton TELEGRAM_BOT_TOKEN dans .env
  2. Lance : python get_chat_id.py
  3. Envoie n'importe quel message à ton bot sur Telegram
  4. Ton chat ID s'affiche ici → copie-le dans TELEGRAM_CHAT_ID dans .env
"""

import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def main() -> None:
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN manquant dans .env")
        return

    from telegram import Bot

    bot = Bot(token=TOKEN)

    print()
    print("=" * 50)
    print("  Envoie un message à ton bot sur Telegram")
    print("  puis appuie sur ENTRÉE ici.")
    print("=" * 50)
    input("  ▶  Appuie sur ENTRÉE après avoir envoyé un message...")

    updates = await bot.get_updates(limit=5)
    if not updates:
        print("\n  ⚠️  Aucun message reçu. Essaie d'envoyer /start à ton bot.")
        return

    print()
    for update in updates:
        if update.message:
            user = update.message.from_user
            chat_id = update.message.chat_id
            print(f"  ✅  Utilisateur : {user.first_name} (@{user.username})")
            print(f"      Chat ID     : {chat_id}")
            print()
            print(f"  → Ajoute dans ton .env :")
            print(f"    TELEGRAM_CHAT_ID={chat_id}")
            break


if __name__ == "__main__":
    asyncio.run(main())
