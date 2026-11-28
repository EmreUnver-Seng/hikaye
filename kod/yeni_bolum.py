"""Bir bölümü baştan sona yürütür; başta her adım için kimin yapacağını sorar.

Kullanım: python kod/yeni_bolum.py bolumler/bolum_NN/senaryo.json

Adımlar sırayla: görseller → seslendirme → montaj → kapak. Her adım için:
  s (sistem)  : bu betik ilgili modülü çalıştırır, kontrol noktalarında bekler.
  k (kendim)  : betik yalnızca komutu gösterir; sen yapıp Enter'a basınca devam eder.
  a (atla)    : adım hiç yapılmaz (ör. zaten hazırsa).
Modüller ayrı süreç olarak çalışır (her biri tek başına çalıştığı gibi).
"""

import subprocess
import sys
from pathlib import Path

KOD = Path(__file__).resolve().parent
KOK = KOD.parent
sys.path.insert(0, str(KOD))

from gorsel import HARFLER, varyant_yolu  # noqa: E402
from senaryo import SenaryoHatasi, senaryo_yukle  # noqa: E402
from ses import dosya_adi  # noqa: E402

ADIMLAR = [
    ("gorsel", "Görseller (Gemini isteği + yerleştirme)"),
    ("ses", "Seslendirme (ElevenLabs)"),
    ("montaj", "Montaj (video.mp4)"),
    ("kapak", "Kapak (kapak.png)"),
]
SECIMLER = {"s": "sistem", "sistem": "sistem", "": "sistem",
            "k": "kendim", "kendim": "kendim",
            "a": "atla", "atla": "atla"}


class Durdur(Exception):
    """Kullanıcı 'dur' dedi."""


# --- Saf yardımcılar (test edilir) ---

def secim_cozumle(cevap):
    """'s'/'k'/'a' (boş = sistem) → 'sistem'/'kendim'/'atla'; geçersizse None."""
    return SECIMLER.get(cevap.strip().lower())


def adim_durumlari(veri, klasor):
    """Her adımın şu anki durumu, soru sırasında yanına yazılır."""
    klasor = Path(klasor)
    gorseller = klasor / "gorseller"
    sahneler = veri["sahneler"]
    hazir_gorsel = sum(varyant_yolu(gorseller, s["no"], "a").exists() for s in sahneler)
    cumleler = [(s["no"], i) for s in sahneler for i in range(1, len(s["cumleler"]) + 1)]
    hazir_ses = sum((klasor / "sesler" / f"{dosya_adi(n, i)}.mp3").exists() for n, i in cumleler)
    return {
        "gorsel": f"{hazir_gorsel}/{len(sahneler)} sahne görseli hazır",
        "ses": f"{hazir_ses}/{len(cumleler)} cümle sesi hazır",
        "montaj": "video.mp4 var" if (klasor / "video.mp4").exists() else "video.mp4 yok",
        "kapak": "kapak.png var" if (klasor / "kapak.png").exists() else "kapak.png yok",
    }


def eksik_sahneler(veri, gorseller):
    return [s["no"] for s in veri["sahneler"]
            if not varyant_yolu(gorseller, s["no"], "a").exists()]


def ek_varyantlar(veri, gorseller):
    """b/c varyantı olan sahneler: {no: ['b', ...]}."""
    sonuc = {}
    for s in veri["sahneler"]:
        ekler = [h for h in HARFLER[1:] if varyant_yolu(gorseller, s["no"], h).exists()]
        if ekler:
            sonuc[s["no"]] = ekler
    return sonuc


def komut(modul, senaryo, *ekler):
    return [sys.executable, str(KOD / f"{modul}.py"), str(senaryo), *ekler]


def komut_metni(modul, senaryo, *ekler):
    """Kullanıcıya gösterilecek kısa biçim."""
    return " ".join(["python", f"kod/{modul}.py", _goreli(senaryo), *ekler])


def _goreli(yol):
    yol = Path(yol).resolve()
    return yol.relative_to(KOK).as_posix() if yol.is_relative_to(KOK) else str(yol)


# --- Etkileşim ---

def sor(metin, girdi=input):
    cevap = girdi(metin).strip()
    if cevap.lower() in ("dur", "q", "çık"):
        raise Durdur
    return cevap


def secimleri_sor(durumlar, girdi=input):
    print("Her adım için kim yapacak?  s = sistem (Enter)   k = kendim   a = atla")
    secimler = {}
    for anahtar, ad in ADIMLAR:
        while True:
            cevap = secim_cozumle(sor(f"  {ad} [{durumlar[anahtar]}]: ", girdi))
            if cevap:
                secimler[anahtar] = cevap
                break
            print("    s, k ya da a yaz.")
    return secimler


def calistir(komut_listesi):
    """Modülü ayrı süreçte çalıştırır (girdi/çıktı bu terminalde). Başarılıysa True."""
    return subprocess.run(komut_listesi, cwd=KOK).returncode == 0


def kendim(baslik, komutlar, girdi=input):
    print(f"\n== {baslik}: sen yapacaksın ==")
    if komutlar:
        print("Gereken komutlar:")
        for k in komutlar:
            print(f"  {k}")
    sor("Bitince Enter'a bas (çıkmak için 'dur'): ", girdi)


# --- Adımlar (sistem) ---

def gorsel_sistem(veri, senaryo, girdi=input):
    gorseller = senaryo.parent / "gorseller"
    print("\n== Görseller ==")
    if not calistir(komut("gorsel", senaryo)):
        raise Durdur
    print(f"\nİstekler: {_goreli(gorseller / 'istekler.md')}")
    while True:
        eksik = eksik_sahneler(veri, gorseller)
        if not eksik:
            print("✓ Bütün sahne görselleri hazır.")
            break
        no = eksik[0]
        print(f"\nEksik sahneler: {', '.join(map(str, eksik))}")
        cevap = sor(f"Sahne {no}: Gemini'de üretip indir, sonra Enter (İndirilenler'deki en yeni) "
                    "ya da dosya yolunu yapıştır; 'geç' = görselleri sonra eklerim: ", girdi)
        if cevap.lower() == "geç":
            print("! Eksik görsel varken montaj hata verir.")
            break
        ekler = [str(no)] + ([cevap.strip('"')] if cevap else [])
        calistir(komut("gorsel", senaryo, "--yerlestir", *ekler))
    print("Alternatif (b/c) eklemek istersen: "
          f"{komut_metni('gorsel', senaryo, '--yerlestir', '<sahne no>')}")
    sor("Görsellerle işin bitince Enter: ", girdi)


def ses_sistem(veri, senaryo, girdi=input):
    print("\n== Seslendirme ==")
    if not calistir(komut("ses", senaryo, "--kuru")):
        raise Durdur
    if sor("Seslendirilsin mi? (e/h): ", girdi).lower() in ("e", "evet"):
        if not calistir(komut("ses", senaryo)):
            raise Durdur
    print(f"\nDinle: {_goreli(senaryo.parent / 'sesler')}")
    while True:
        cevap = sor("Yeniden üretilecek cümle (ör. 3.2), 'kart' ya da Enter = devam: ", girdi)
        if not cevap:
            break
        ekler = ["--kart"] if cevap.lower() == "kart" else ["--cumle", cevap]
        calistir(komut("ses", senaryo, *ekler))


def montaj_sistem(veri, senaryo, girdi=input):
    print("\n== Montaj ==")
    ekler = []
    varyantlar = ek_varyantlar(veri, senaryo.parent / "gorseller")
    if varyantlar:
        print("Alternatif görseli olan sahneler: "
              + ", ".join(f"{no} (a, {', '.join(h)})" for no, h in varyantlar.items()))
        secim = sor("Kullanılacak varyantlar (ör. 3=b,5=c; Enter = hepsi a): ", girdi)
        if secim:
            ekler = ["--varyant", secim]
    while not calistir(komut("montaj", senaryo, *ekler)):
        if sor("Montaj başarısız. Düzeltip yeniden denemek için Enter, bırakmak için 'dur': ",
               girdi):
            break


def kapak_sistem(veri, senaryo, girdi=input):
    print("\n== Kapak ==")
    secim = sor("Kapak arka planı (ör. 4=b; Enter = sahne 1/a): ", girdi)
    calistir(komut("kapak", senaryo, *(["--gorsel", secim] if secim else [])))


SISTEM = {"gorsel": gorsel_sistem, "ses": ses_sistem,
          "montaj": montaj_sistem, "kapak": kapak_sistem}


def kendi_komutlari(senaryo):
    return {
        "gorsel": [komut_metni("gorsel", senaryo),
                   komut_metni("gorsel", senaryo, "--yerlestir", "<sahne no>", "[dosya]")],
        "ses": [komut_metni("ses", senaryo),
                komut_metni("ses", senaryo, "--cumle", "3.2")],
        "montaj": [komut_metni("montaj", senaryo, "[--varyant 3=b]")],
        "kapak": [komut_metni("kapak", senaryo, "[--gorsel 4=b]")],
    }


def main(argv, girdi=input):
    if len(argv) != 1:
        print("Kullanım: python kod/yeni_bolum.py bolumler/bolum_NN/senaryo.json")
        return 1
    senaryo = Path(argv[0]).resolve()
    if not calistir(komut("senaryo", senaryo)):
        return 1
    veri = senaryo_yukle(senaryo)
    print()
    try:
        secimler = secimleri_sor(adim_durumlari(veri, senaryo.parent), girdi)
        komutlar = kendi_komutlari(senaryo)
        for anahtar, ad in ADIMLAR:
            if secimler[anahtar] == "sistem":
                SISTEM[anahtar](veri, senaryo, girdi)
            elif secimler[anahtar] == "kendim":
                kendim(ad, komutlar[anahtar], girdi)
    except (Durdur, EOFError, KeyboardInterrupt):
        print("\nDurduruldu. Kaldığın yerden devam etmek için yeniden çalıştır; "
              "hazır adımlar için 'a' (atla) seç.")
        return 1
    except SenaryoHatasi as e:
        print(f"✗ Senaryo geçersiz: {e}")
        return 1
    print(f"\n✓ Bölüm {veri['bolum']} hazır: {_goreli(senaryo.parent)}")
    print("Yükledikten ve oylama kapandıktan sonra kazanan seçimi durum.json'a gir.")
    return 0


if __name__ == "__main__":
    # Windows konsolunda Türkçe karakterler ve ✓ işareti bozulmasın.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
