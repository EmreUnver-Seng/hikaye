"""Bu cihazdaki kurulumun eksiksiz olup olmadığını kontrol eder (Mac ve Windows).

Çalıştırma:
    Mac:     .venv/bin/python kod/kurulum_kontrol.py
    Windows: .venv\\Scripts\\python kod\\kurulum_kontrol.py

Çıktıyı Claude'a yapıştırabilirsin: anahtarlar, e-posta gibi gizli bilgiler yazdırılmaz.
"""

import importlib.util
import locale
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sorunlar: list[str] = []


def satir(tamam: bool, baslik: str, detay: str = "", cozum: str = "") -> None:
    isaret = "OK  " if tamam else "HATA"
    print(f"[{isaret}] {baslik}" + (f" - {detay}" if detay else ""))
    if not tamam:
        sorunlar.append(f"{baslik}: {cozum}" if cozum else baslik)


def git(*args: str) -> str:
    try:
        sonuc = subprocess.run(
            ["git", *args], cwd=KOK, capture_output=True, text=True, encoding="utf-8"
        )
        return sonuc.stdout.strip()
    except FileNotFoundError:
        return ""


def main() -> None:
    print(f"Sistem: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Proje klasörü: {KOK}")
    print()

    # Python
    surum = sys.version_info
    satir(surum >= (3, 11), "Python 3.11+", f"{surum.major}.{surum.minor}.{surum.micro}",
          "uv venv --python 3.12")
    sanal = sys.prefix != sys.base_prefix
    satir(sanal and Path(sys.prefix).name == ".venv", "Proje sanal ortamı (.venv)",
          sys.prefix, ".venv içindeki python ile çalıştır")

    # Paketler
    for modul, paket in [("google.genai", "google-genai"), ("elevenlabs", "elevenlabs"),
                         ("dotenv", "python-dotenv")]:
        try:
            var = importlib.util.find_spec(modul) is not None
        except ModuleNotFoundError:
            var = False
        satir(var, f"Paket: {paket}", cozum="uv pip install -r requirements.txt")

    # Dış araçlar
    satir(bool(shutil.which("ffmpeg")), "ffmpeg", cozum="Mac: brew install ffmpeg / Windows: winget install Gyan.FFmpeg")
    satir(bool(shutil.which("git")), "git")

    # Proje dosyaları
    for dosya in ["CLAUDE.md", "KULLANIM.md", "hikaye.md", "requirements.txt", ".gitignore", ".gitattributes"]:
        satir((KOK / dosya).exists(), f"Dosya: {dosya}", cozum="git pull")

    # .env
    env = KOK / ".env"
    if env.exists():
        icerik = {}
        for s in env.read_text(encoding="utf-8").splitlines():
            if "=" in s and not s.strip().startswith("#"):
                ad, deger = s.split("=", 1)
                icerik[ad.strip()] = deger.strip()
        for ad in ["GEMINI_API_KEY", "ELEVENLABS_API_KEY"]:
            dolu = bool(icerik.get(ad))
            satir(dolu, f".env: {ad}", "dolu" if dolu else "boş",
                  "anahtarı şifre yöneticisinden yapıştır")
    else:
        satir(False, ".env dosyası", "yok", ".env.example dosyasını .env adıyla kopyala, anahtarları yaz")

    # Git
    satir((KOK / ".git").exists(), "Git deposu", cozum="gh repo clone EmreUnver-Seng/hikaye")
    uzak = git("remote", "get-url", "origin")
    satir("EmreUnver-Seng/hikaye" in uzak, "GitHub bağlantısı (origin)", uzak or "yok")
    email = git("config", "user.email")
    satir(email.endswith("@users.noreply.github.com"), "Git e-postası noreply",
          "ayarlı" if email else "ayarsız",
          'git config user.email "255063380+EmreUnver-Seng@users.noreply.github.com"')
    satir(bool(git("config", "user.name")), "Git kullanıcı adı", cozum='git config user.name "Emre"')
    degisen = git("status", "--porcelain")
    satir(not degisen, "Çalışma alanı temiz", f"{len(degisen.splitlines())} değişmiş dosya" if degisen else "",
          "git status ile bak; satır sonu sorunu olabilir")
    git("fetch", "-q")
    geride = git("rev-list", "--count", "HEAD..origin/main")
    satir(geride in ("", "0"), "GitHub ile güncel", f"{geride} commit geride" if geride not in ("", "0") else "",
          "git pull")

    # Windows'a özel
    if platform.system() == "Windows":
        satir(os.environ.get("PYTHONUTF8") == "1", "PYTHONUTF8=1",
              cozum='[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User") ve terminali yeniden aç')
        satir("onedrive" not in str(KOK).lower(), "Proje OneDrive dışında",
              cozum="projeyi C:\\Users\\<ad>\\hikaye gibi bir yere klonla")
        print(f"       (bilgi) Varsayılan kodlama: {locale.getpreferredencoding(False)}")

    print()
    if sorunlar:
        print(f"{len(sorunlar)} sorun bulundu:")
        for s in sorunlar:
            print(f"  - {s}")
    else:
        print("Kurulum eksiksiz. API anahtarlarını denemek için: kod/test_anahtarlar.py")


if __name__ == "__main__":
    main()
