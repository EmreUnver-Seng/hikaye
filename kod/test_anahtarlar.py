"""API anahtarlarının ve ffmpeg'in çalıştığını kontrol eder.

Çalıştırma:  .venv/bin/python kod/test_anahtarlar.py
Anahtarların kendisini asla ekrana yazmaz.
"""

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

KOK = Path(__file__).resolve().parent.parent
load_dotenv(KOK / ".env")


def test_gemini() -> bool:
    anahtar = os.getenv("GEMINI_API_KEY")
    if not anahtar:
        print("❌ Gemini: GEMINI_API_KEY .env içinde boş")
        return False
    try:
        from google import genai

        client = genai.Client(api_key=anahtar)
        modeller = [m.name for m in client.models.list()]
        gorsel = [m for m in modeller if "image" in m.lower()]
        print(f"✅ Gemini: anahtar çalışıyor ({len(modeller)} model erişilebilir)")
        if gorsel:
            print("   Görsel modelleri:", ", ".join(sorted(gorsel)))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ Gemini: {type(e).__name__}: {e}")
        return False


def test_elevenlabs() -> bool:
    anahtar = os.getenv("ELEVENLABS_API_KEY")
    if not anahtar:
        print("❌ ElevenLabs: ELEVENLABS_API_KEY .env içinde boş")
        return False
    try:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=anahtar)
        abonelik = client.user.subscription.get()
        print(
            f"✅ ElevenLabs: anahtar çalışıyor (plan: {abonelik.tier}, "
            f"bu ay kullanılan karakter: {abonelik.character_count}/{abonelik.character_limit})"
        )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ ElevenLabs: {type(e).__name__}: {e}")
        return False


def test_ffmpeg() -> bool:
    if shutil.which("ffmpeg"):
        print("✅ ffmpeg: kurulu")
        return True
    print("❌ ffmpeg: bulunamadı (brew install ffmpeg)")
    return False


if __name__ == "__main__":
    sonuclar = [test_gemini(), test_elevenlabs(), test_ffmpeg()]
    print()
    print("Hepsi hazır 🎉" if all(sonuclar) else "Bazı kontroller başarısız, yukarıya bak.")
