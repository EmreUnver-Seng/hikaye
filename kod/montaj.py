"""Montaj adımı: görselleri, cümle seslerini ve altyazıyı dikey videoda birleştirir.

Her sahne yavaş zoom'lu bir klip olur; cümle sesleri arka arkaya dizilir; o an
söylenen kelimesi vurgulu altyazı ve sonda ikilem (seçenek) kartı eklenir.
Kartı anlatıcı okur (sesler/kart.mp3, ses.py üretir; yoksa kart sessiz kalır).
Senaryodaki 'kanca' açılış sahnesi (1. sahne) boyunca ekranın üstünde kısa bir yazı olarak görünür.
Ses, sonda iki geçişli loudnorm ile -14 LUFS'a getirilir (video yeniden kodlanmaz).
Seçim kartında A ve B yan yana iki yuvarlak köşeli kart olur; kartın üstünde
seçenek görseli (gorseller/secenek_A.png), altında harf ve metin. Görsel yoksa
yerinde büyük harf durur.
Senaryo sırayla gezilir (zamanlama.json'daki eski kayıtlar yok sayılır), cümle
süreleri mp3'lerin gerçek uzunluğundan (ffprobe) alınır.

Kullanım:
    python kod/montaj.py bolumler/bolum_01/senaryo.json                 # tam bölüm → video.mp4
    python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 3       # önizleme → onizleme.mp4
    python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 1-3 --varyant 1=b,3=c
    python kod/montaj.py bolumler/bolum_01/senaryo.json --kuru          # render yok, yalnızca plan

Tasarım: docs/superpowers/specs/2026-11-26-montaj-design.md
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import (SenaryoHatasi, kart_okuma_metni, kelime_kok,  # noqa: E402
                     secenek_gorseli, secenek_metni, senaryo_yukle)
from ses import KART, SesHatasi, dosya_adi, kayitlari_yukle  # noqa: E402

KOK = Path(__file__).resolve().parent.parent

# --- Font (değiştirmek için: dosyayı varliklar/fontlar/ içine koy, bu iki satırı düzelt) ---
FONT_DOSYASI = "Montserrat-ExtraBold.ttf"
FONT_ADI = "Montserrat ExtraBold"  # fontun içindeki aile adı
FONT_KLASORU = KOK / "varliklar" / "fontlar"

GEN, YUK, FPS = 1080, 1920, 30
CUMLE_ARASI = 0.45   # aynı sahnede cümleler arası sessizlik (sn)
SAHNE_SONU = 0.7     # sahnenin son cümlesinden sonra (sn)
BUYUTME = 4          # zoom'dan önce görselin büyütülme katı (titremeyi önler)
KART_SURESI = 4.0
ZOOM = 1.08          # tek sahneler 1→ZOOM yakınlaşır, çiftler ZOOM→1 uzaklaşır
KART_KARARTMA = 0.4  # kart görselinin parlaklık çarpanı (%60 karartma)
HEDEF_SURE = (45, 90)
HARFLER = ("a", "b", "c")

GRUP_KELIME = 4
GRUP_KARAKTER = 22
CUMLE_SONU_PAYI = 0.3  # cümlenin son kelimesi bittikten sonra altyazının kalma süresi
BEYAZ = "&H00FFFFFF&"
VURGU = "&H002DB8E8&"  # hardal sarısı #E8B82D (ASS: &HAABBGGRR)
KART_GECIKME = 0.25  # kart içeriği (soru, kartlar, yazılar) bu kadar sonra belirmeye başlar
KART_BELIRME = 0.4   # belirme (fade in) süresi: kararma, kartlar ve yazılar birlikte
_FAD = f"\\fad({round(KART_BELIRME * 1000)},0)"
KART_SES_BAS = KART_GECIKME + KART_BELIRME  # anlatıcı, kart belirdikten sonra okumaya başlar
KART_SES_SONU = 1.5  # okuma bittikten sonra kartın ekranda kalma süresi (yorum yazma payı)

# --- Kanca yazısı (kural 2026-11-28: açılış sahnesi boyunca, ilk kareden itibaren) ---
KANCA_BAS = 0.0                   # sn; ilk karede görünür (belirme geçişi yok)
KANCA_KAYBOLMA = 450              # ms; açılış sahnesinin sonunda kaybolma geçişi
KANCA_Y = 300                     # üst üçte bir; platform arayüzünün altında kalır
KANCA_SATIR = 22                  # satır başına en fazla karakter

# --- Ses yüksekliği (TikTok/Reels için) ---
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=20"  # geniş LRA: doğrusal mod korunur

# --- Seçim kartı düzeni (1080×1920 üzerinde piksel) ---
KART_GEN, KART_YUK = 450, 640       # her seçenek kartı
KART_XLER = (60, 570)                # A solda, B sağda
KART_Y = 760
KART_YARICAP = 36
KART_KENAR = 4                       # hardal sarısı kenar çizgisi kalınlığı
KART_ZEMIN = ((13, 16, 32), 220)     # koyu lacivert, ~%86 opak (RGB, alfa 0–255)
KART_VURGU_RGB = (232, 184, 45)      # #E8B82D
KART_GORSEL = 410                    # seçenek görseli kare kenarı
KART_IC_PAY = 20                     # kart kenarı ile görsel arası
KART_GORSEL_YARICAP = 24
YEDEK_ZEMIN = ((35, 42, 72), 210)    # görsel yoksa harfin arkasındaki kare
KART_METIN_Y = KART_Y + KART_IC_PAY + KART_GORSEL + 18
KART_HARF_BOYU = 68
KART_SATIR = 14                      # kart metninde satır başına en fazla karakter
SORU_ALT_Y = 700                     # soru bu çizgiye alttan dayanır (yukarı doğru büyür)
CAGRI_Y = KART_Y + KART_YUK + 90
SECENEK_HARFLERI = ("A", "B")

# --- Saat animasyonu (senaryoda sahnenin 'saat' alanı) ---
SAAT_BOYUT = 420                    # kare katman kenarı (px)
SAAT_X, SAAT_Y = (GEN - SAAT_BOYUT) // 2, 190   # üst-orta
SAAT_YARICAP = 196                  # kadran yarıçapı
SAAT_KENAR = 9                      # hardal sarısı çember kalınlığı
SAAT_ZEMIN = ((13, 16, 32), 225)    # koyu lacivert, kart zeminiyle aynı ton
SAAT_MUREKKEP = KART_VURGU_RGB      # çentikler, ibreler, çember
SAAT_YELKOVAN = (165, 9)            # uzunluk, kalınlık (px)
SAAT_AKREP = (105, 15)
SAAT_BELIRME = 0.3                  # başta belirme / sonda kaybolma (sn)
SAAT_BEKLE = 1.0                    # ibreler durduktan sonra ekranda kalma (sn)

# --- Ambiyans: sahnenin 'mekan'ına göre varliklar/ambiyans/<mekan>.mp3 döngüsü ---
AMBIYANS_KLASORU = KOK / "varliklar" / "ambiyans"
AMBIYANS_DB = -12      # dosyalar ~-24 LUFS'a ayarlı; videoda anlatımın çok altında kalır
AMBIYANS_GECIS = 0.6   # mekân değişince iki sesin birbirine geçiş süresi (sn)
# Konuşma sırasında ambiyansı kısar (sidechain ducking)
AMBIYANS_KISMA = "sidechaincompress=threshold=0.03:ratio=3:attack=40:release=500"

KODLAMA = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", str(FPS)]

CumleGirdisi = namedtuple("CumleGirdisi", "anahtar mp3 kelimeler")
# saat: SaatGirdisi ya da None
SahneGirdisi = namedtuple("SahneGirdisi", "no gorsel cumleler saat", defaults=(None,))
# bas_dk: başlangıç (gece yarısından dakika), fark_dk: işaretli dönüş (geri < 0),
# cumle: 0'dan sıra, kelime_bas: ibrelerin durduğu kelimenin cümle içindeki başlangıcı (sn)
SaatGirdisi = namedtuple("SaatGirdisi", "bas_dk fark_dk cumle kelime_bas es")
# Sahne klibine göre (0 = sahne başı): durus = ibrelerin durduğu an, sure = katman süresi
SaatPlani = namedtuple("SaatPlani", "bas_dk fark_dk durus sure")
# sahneler: (no, gorsel, baslangic, kare); cumleler: (anahtar, mp3, baslangic, slot_bitis, kelimeler)
# saatler: {sahne no: SaatPlani}
# kart_sesli: kartta anlatıcı okuması var (ses girdisi cümlelerden hemen sonra gelir)
Cizelge = namedtuple("Cizelge", "sahneler cumleler kart_baslangic kart_kare toplam saatler "
                     "kart_sesli", defaults=({}, False))
# Seçim kartındaki bir seçenek: gorsel = secenek_X.png yolu ya da None (yedek düzen);
# tarif = senaryodaki görsel tarifi var mı (yoksa eksik görsel için uyarı verilmez).
KartSecenegi = namedtuple("KartSecenegi", "harf metin gorsel tarif")
# Bir ambiyans parçası: aynı mekândaki ardışık sahneler tek parça; bas/bit video üzerinde (sn)
Ambiyans = namedtuple("Ambiyans", "mekan dosya bas bit")


class MontajHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek hata (bir veya birden fazla satır)."""

    def __init__(self, hatalar):
        self.hatalar = [hatalar] if isinstance(hatalar, str) else list(hatalar)
        super().__init__("\n".join(self.hatalar))


# --- Bayraklar ---

def _sahne_nolari(veri):
    return [s["no"] for s in veri["sahneler"]]


def sahne_secimi(metin, veri):
    """--sahne değeri ('3', '1-3') → sahne numaraları listesi; None → hepsi."""
    nolar = _sahne_nolari(veri)
    if metin is None:
        return nolar
    eslesme = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", metin)
    if not eslesme:
        raise MontajHatasi(f"--sahne '{metin}' anlaşılmadı. Örnek: --sahne 3 veya --sahne 1-3")
    bas = int(eslesme.group(1))
    bit = int(eslesme.group(2) or bas)
    if bas > bit:
        raise MontajHatasi(f"--sahne '{metin}': aralık ters (önce küçük sayı).")
    for no in (bas, bit):
        if no not in nolar:
            raise MontajHatasi(f"--sahne: {no}. sahne senaryoda yok (sahneler 1–{max(nolar)}).")
    return [no for no in nolar if bas <= no <= bit]


def varyant_secimi(metin, veri):
    """--varyant değeri ('3=b,5=c') → {3: 'b', 5: 'c'}; None → {} (hepsi 'a')."""
    if metin is None:
        return {}
    nolar = _sahne_nolari(veri)
    secim = {}
    for parca in metin.split(","):
        eslesme = re.fullmatch(r"\s*(\d+)\s*=\s*([A-Za-z])\s*", parca)
        if not eslesme or eslesme.group(2).lower() not in HARFLER:
            raise MontajHatasi(f"--varyant '{parca.strip()}' anlaşılmadı. Örnek: --varyant 3=b,5=c "
                               "(harf a, b veya c).")
        no = int(eslesme.group(1))
        if no not in nolar:
            raise MontajHatasi(f"--varyant: {no}. sahne senaryoda yok (sahneler 1–{max(nolar)}).")
        secim[no] = eslesme.group(2).lower()
    return secim


# --- Girdiler ---

def _goster(yol):
    """Mesajlarda kısa yol: proje içindeyse göreli, '/' ayraçlı."""
    try:
        return Path(yol).resolve().relative_to(KOK).as_posix()
    except ValueError:
        return Path(yol).as_posix()


def girdileri_topla(veri, klasor, sahneler, varyantlar):
    """Seçilen sahnelerin görsel ve ses dosyalarını senaryo sırasıyla toplar.

    Eksik görsel, ses, kelime zamanlaması ve metni değişmiş (eski) sesler hep
    birlikte tek MontajHatasi ile bildirilir.
    """
    klasor = Path(klasor)
    try:
        kayitlar = kayitlari_yukle(klasor / "sesler")
    except SesHatasi as e:
        raise MontajHatasi(e.hatalar) from e
    senaryo = _goster(klasor / "senaryo.json")
    hatalar, girdiler = [], []
    for sahne in veri["sahneler"]:
        no = sahne["no"]
        if no not in sahneler:
            continue
        gorsel = klasor / "gorseller" / f"sahne{no}_{varyantlar.get(no, 'a')}.png"
        if not gorsel.is_file():
            hatalar.append(f"Sahne {no}: görsel yok ({gorsel.name}). Üret ve yerleştir: "
                           f"python kod/gorsel.py {senaryo} --yerlestir {no}")
        cumleler, ses_sorunu = [], False
        for i, cumle in enumerate(sahne["cumleler"], 1):
            anahtar = dosya_adi(no, i)
            mp3 = klasor / "sesler" / f"{anahtar}.mp3"
            kayit = kayitlar.get(anahtar)
            konum = f"Sahne {no}, cümle {i}"
            if not mp3.is_file():
                hatalar.append(f"{konum}: ses dosyası yok ({anahtar}.mp3).")
                ses_sorunu = True
            if kayit is None:
                hatalar.append(f"{konum}: kelime zamanlaması yok ({anahtar}, zamanlama.json).")
                ses_sorunu = True
            elif kayit.get("metin") != cumle["metin"]:
                hatalar.append(f"{konum}: ses eski ({anahtar}): kayıttaki metin senaryodakiyle "
                               "aynı değil.")
                ses_sorunu = True
            kelimeler = (kayit or {}).get("kelimeler") or []
            cumleler.append(CumleGirdisi(anahtar, mp3, kelimeler))
        if ses_sorunu:
            hatalar.append(f"Sahne {no} seslerini üret: python kod/ses.py {senaryo} --sahne {no}")
        saat = None
        if "saat" in sahne and not ses_sorunu:
            saat = saat_girdisi(sahne["saat"], cumleler[sahne["saat"]["cumle"] - 1].kelimeler)
            if saat is None:
                hatalar.append(f"Sahne {no}, saat: '{sahne['saat']['kelime']}' kelimesi "
                               f"zamanlama.json'da bulunamadı (cümle {sahne['saat']['cumle']}).")
        girdiler.append(SahneGirdisi(no, gorsel, cumleler, saat))
    if hatalar:
        raise MontajHatasi(hatalar)
    return girdiler


def kart_sesi(veri, klasor):
    """Seçim kartı okumasının mp3'ü ve (varsa) uyarı. Okuma yoksa ya da eskiyse mp3 None."""
    klasor = Path(klasor)
    mp3 = klasor / "sesler" / f"{KART}.mp3"
    komut = f"python kod/ses.py {_goster(klasor / 'senaryo.json')} --kart"
    try:
        kayit = kayitlari_yukle(klasor / "sesler").get(KART)
    except SesHatasi:
        kayit = None
    if not mp3.is_file() or kayit is None:
        return None, f"Kart okuması yok, kart sessiz kalır. Üret: {komut}"
    if kayit.get("metin") != kart_okuma_metni(veri["ikilem"]):
        return None, f"Kart okuması eski (ikilem değişmiş), kart sessiz kalır. Üret: {komut}"
    return mp3, None


def _dakika(metin):
    ss, dd = metin.split(":")
    return int(ss) * 60 + int(dd)


def saat_girdisi(saat, kelimeler):
    """Senaryodaki 'saat' alanı + cümlenin kelime zamanlamaları → SaatGirdisi.

    İbreler, cümlede `kelime` ile eşleşen ilk kelimenin başlangıcında durur; kelime
    zamanlamalarda yoksa None.
    """
    aranan = kelime_kok(saat["kelime"])
    bulunan = next((k for k in kelimeler if kelime_kok(k["kelime"]) == aranan), None)
    if bulunan is None:
        return None
    bas, bit = _dakika(saat["bas"]), _dakika(saat["bit"])
    fark = (bit - bas) % 1440 if saat["yon"] == "ileri" else -((bas - bit) % 1440)
    return SaatGirdisi(bas, fark, saat["cumle"] - 1, bulunan["baslangic"], saat.get("es", 0))


# --- Zaman çizelgesi ---

def zaman_cizelgesi(girdiler, sureler, kart_sure=None):
    """Sahne ve cümlelerin video üzerindeki yerleri.

    Sahne süresi kareye yuvarlanır; sahne başlangıçları önceki karelerin
    toplamından hesaplanır, böylece ses ile görüntü arasında kayma birikmez.
    kart_sure: kart okumasının süresi (sn); verilirse kart, okuma bitene kadar uzar.
    """
    sahneler, cumleler, saatler = [], [], {}
    kare_toplam = 0
    for g in girdiler:
        bas = kare_toplam / FPS
        ofsetler, t = [], (g.saat.es if g.saat else 0.0)
        for c in g.cumleler:
            ofsetler.append(t)
            t += sureler[c.anahtar] + CUMLE_ARASI
        sure = t - CUMLE_ARASI + SAHNE_SONU
        kare = round(sure * FPS)
        bitis = (kare_toplam + kare) / FPS
        for j, c in enumerate(g.cumleler):
            slot = bas + ofsetler[j + 1] if j + 1 < len(ofsetler) else bitis
            cumleler.append((c.anahtar, c.mp3, bas + ofsetler[j], slot, c.kelimeler))
        sahneler.append((g.no, g.gorsel, bas, kare))
        if g.saat:
            durus = ofsetler[g.saat.cumle] + g.saat.kelime_bas
            sure = min(durus + SAAT_BEKLE + SAAT_BELIRME, kare / FPS)
            saatler[g.no] = SaatPlani(g.saat.bas_dk, g.saat.fark_dk, durus, sure)
        kare_toplam += kare
    kart_sn = KART_SURESI if kart_sure is None else max(
        KART_SURESI, KART_SES_BAS + kart_sure + KART_SES_SONU)
    kart_kare = round(kart_sn * FPS)
    kart_bas = kare_toplam / FPS
    return Cizelge(sahneler, cumleler, kart_bas, kart_kare, (kare_toplam + kart_kare) / FPS,
                   saatler, kart_sure is not None)


# --- Altyazı ---

def _cumle_sonu_mu(kelime):
    return kelime.rstrip("\"'»”’)").endswith((".", "?", "!", "…"))


def gruplara_bol(kelimeler):
    """Kelimeleri ekranda birlikte duracak 1–4 kelimelik gruplara böler."""
    gruplar, grup = [], []
    for k in kelimeler:
        metin = " ".join(x["kelime"] for x in grup + [k])
        if grup and (len(grup) >= GRUP_KELIME or len(metin) > GRUP_KARAKTER):
            gruplar.append(grup)
            grup = []
        grup.append(k)
        if _cumle_sonu_mu(k["kelime"]) or (k["kelime"].endswith(",") and len(grup) >= 2):
            gruplar.append(grup)
            grup = []
    if grup:
        gruplar.append(grup)
    return gruplar


def ass_zaman(sn):
    cs = round(max(sn, 0) * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_kacir(metin):
    """ASS'de özel anlamı olan karakterleri zararsız hâle getirir."""
    return (metin.replace("\\", "/").replace("{", "(").replace("}", ")")
            .replace("\r", " ").replace("\n", " "))


def _olay(bas, bit, stil, metin):
    return f"Dialogue: 0,{ass_zaman(bas)},{ass_zaman(bit)},{stil},,0,0,0,,{metin}"


def altyazi_olaylari(cizelge):
    """Her kelime için bir olay: grubu gösterir, o kelime vurgulu."""
    olaylar = []
    for _anahtar, _mp3, bas, slot, kelimeler in cizelge.cumleler:
        gruplar = gruplara_bol(kelimeler)
        for gi, grup in enumerate(gruplar):
            sonraki_grup = gruplar[gi + 1][0]["baslangic"] if gi + 1 < len(gruplar) else None
            for ki, k in enumerate(grup):
                if ki + 1 < len(grup):
                    bitis = bas + grup[ki + 1]["baslangic"]
                elif sonraki_grup is not None:
                    bitis = bas + sonraki_grup
                else:
                    bitis = min(bas + k["bitis"] + CUMLE_SONU_PAYI, slot)
                parcalar = [
                    f"{{\\c{VURGU}}}{ass_kacir(x['kelime'])}{{\\c{BEYAZ}}}" if x is k
                    else ass_kacir(x["kelime"])
                    for x in grup]
                olaylar.append(_olay(bas + k["baslangic"], bitis, "Alt", " ".join(parcalar)))
    return olaylar


def kart_plani(ikilem, gorsel_klasoru):
    """İkilemdeki seçenekler (A, B sırasıyla); görsel dosyası varsa yolu, yoksa None."""
    secenekler = ikilem.get("secenekler") or {}
    plan = []
    for harf in SECENEK_HARFLERI:
        if harf not in secenekler:
            continue
        yol = Path(gorsel_klasoru) / f"secenek_{harf}.png"
        plan.append(KartSecenegi(harf, secenek_metni(secenekler[harf]),
                                 yol if yol.is_file() else None,
                                 bool(secenek_gorseli(secenekler[harf]))))
    return plan


def satirlara_bol(metin, sinir=KART_SATIR):
    """Metni kelime bölmeden en fazla `sinir` karakterlik satırlara ayırır."""
    satirlar = []
    for kelime_ in metin.split():
        if satirlar and len(satirlar[-1]) + 1 + len(kelime_) <= sinir:
            satirlar[-1] += " " + kelime_
        else:
            satirlar.append(kelime_)
    return satirlar


def _kart_merkezi(i):
    return KART_XLER[i] + KART_GEN // 2


def _kart_metnini_sigdir(metin, gorselli):
    """Metni kartın iç genişliğine ve alt bölümde kalan yüksekliğe sığdır."""
    genislik = KART_GEN - 2 * KART_IC_PAY - 4
    ayrilan = 86 if gorselli else 20  # harf satırı veya yedek düzende üst boşluk
    yukseklik = KART_Y + KART_YUK - KART_METIN_Y - ayrilan - KART_IC_PAY
    kelimeler = metin.split()
    for boy in range(48, 0, -1):
        font = ImageFont.truetype(str(FONT_KLASORU / FONT_DOSYASI), boy)
        if any(font.getlength(kelime) > genislik for kelime in kelimeler):
            continue
        satirlar = []
        for kelime in kelimeler:
            aday = f"{satirlar[-1]} {kelime}" if satirlar else kelime
            if satirlar and font.getlength(aday) <= genislik:
                satirlar[-1] = aday
            else:
                satirlar.append(kelime)
        if len(satirlar) * sum(font.getmetrics()) <= yukseklik:
            return boy, "\\N".join(ass_kacir(satir) for satir in satirlar)
    raise MontajHatasi("Seçenek metni karta sığmıyor.")


def kart_olaylari(ikilem, baslangic, sure, plan=None):
    """Seçenek kartının yazıları: soru, kartlardaki harf + metin ve yorum çağrısı.

    plan: kart_plani() sonucu; verilmezse seçenekler görselsiz (yedek düzen) sayılır.
    """
    if plan is None:
        plan = [KartSecenegi(h, secenek_metni(m), None, False)
                for h, m in (ikilem.get("secenekler") or {}).items() if h in SECENEK_HARFLERI]
    bitis = baslangic + sure
    gec = baslangic + KART_GECIKME
    soru = ass_kacir(ikilem["soru"])
    if plan:
        olaylar = [_olay(gec, bitis, "Soru", f"{{\\an2\\pos(540,{SORU_ALT_Y}){_FAD}}}{soru}")]
    else:
        olaylar = [_olay(gec, bitis, "Soru", f"{{\\an5\\pos(540,860){_FAD}}}{soru}")]
    for i, k in enumerate(plan):
        x = _kart_merkezi(i)
        boy, metin = _kart_metnini_sigdir(k.metin, k.gorsel is not None)
        if k.gorsel is None:  # yedek düzen: görselin yerinde büyük harf, altta yalnızca metin
            orta = KART_Y + KART_IC_PAY + KART_GORSEL // 2
            olaylar.append(_olay(gec, bitis, "Harf",
                                 f"{{\\an5\\pos({x},{orta}){_FAD}\\c{VURGU}}}{k.harf}"))
            olaylar.append(_olay(gec, bitis, "Kart",
                                 f"{{\\an8\\pos({x},{KART_METIN_Y + 20}){_FAD}\\fs{boy}}}{metin}"))
        else:
            olaylar.append(_olay(
                gec, bitis, "Kart",
                f"{{\\an8\\pos({x},{KART_METIN_Y}){_FAD}}}"
                f"{{\\fs{KART_HARF_BOYU}\\c{VURGU}}}{k.harf}{{\\fs{boy}\\c{BEYAZ}}}\\N{metin}"))
    cagri = "Yorumlara A ya da B yaz" if plan else "Yorumlara yaz"
    y = CAGRI_Y if plan else 1100
    olaylar.append(_olay(gec, bitis, "Not", f"{{\\an5\\pos(540,{y}){_FAD}}}{cagri}"))
    return olaylar


def kanca_olaylari(kanca, cizelge):
    """'kanca' yazısı: video 1. sahneyle başlıyorsa, ilk kareden 1. sahnenin sonuna kadar, üstte."""
    if not kanca or not cizelge.sahneler or cizelge.sahneler[0][0] != 1:
        return []
    _no, _gorsel, bas, kare = cizelge.sahneler[0]
    bit = bas + kare / FPS
    metin = "\\N".join(ass_kacir(s) for s in satirlara_bol(kanca.strip(), KANCA_SATIR))
    return [_olay(KANCA_BAS, bit, "Kanca",
                  f"{{\\an8\\pos(540,{KANCA_Y})\\fad(0,{KANCA_KAYBOLMA})}}{metin}")]


def ass_metni(cizelge, ikilem, plan=None, kanca=None):
    stil = ("Style: {ad},{font},{boy},&H00FFFFFF,&H00FFFFFF,{kontur_renk},&H80000000,"
            "0,0,0,0,100,100,0,0,{kenar},{kontur},{golge},{hiza},{yan},{yan},{alt},1")
    stiller = [
        stil.format(ad="Alt", font=FONT_ADI, boy=86, kontur_renk="&H00000000", kenar=1,
                    kontur=7, golge=3, hiza=2, yan=80, alt=420),
        stil.format(ad="Soru", font=FONT_ADI, boy=72, kontur_renk="&H00000000", kenar=1,
                    kontur=6, golge=2, hiza=5, yan=90, alt=0),
        stil.format(ad="Kart", font=FONT_ADI, boy=48, kontur_renk="&H00000000", kenar=1,
                    kontur=3, golge=0, hiza=8, yan=0, alt=0),
        stil.format(ad="Harf", font=FONT_ADI, boy=260, kontur_renk="&H00000000", kenar=1,
                    kontur=0, golge=0, hiza=5, yan=0, alt=0),
        stil.format(ad="Not", font=FONT_ADI, boy=48, kontur_renk="&H00000000", kenar=1,
                    kontur=4, golge=2, hiza=5, yan=90, alt=0),
        stil.format(ad="Kanca", font=FONT_ADI, boy=62, kontur_renk="&H00000000", kenar=1,
                    kontur=5, golge=2, hiza=8, yan=90, alt=0),
    ]
    olaylar = kanca_olaylari(kanca, cizelge) + altyazi_olaylari(cizelge) + kart_olaylari(
        ikilem, cizelge.kart_baslangic, cizelge.kart_kare / FPS, plan)
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {GEN}", f"PlayResY: {YUK}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *stiller, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *olaylar, ""])


# --- ffmpeg komutları (ilk eleman program adı; çalıştırırken PATH'ten bulunur) ---

def saat_filtresi(plan):
    """Saydam zeminli, SAAT_BOYUT kare analog saat katmanı (ffmpeg kaynak + geq).

    Sahne başında belirir; ibreler plan.bas_dk'dan başlayıp plan.fark_dk kadar döner
    (yavaşlayarak, ease-out) ve plan.durus anında durur; SAAT_BEKLE sonra kaybolur.
    T = katmanın zamanı (sahne başı 0). Her piksel için ld(5)=mürekkep (ibre, çentik,
    çember), ld(6)=kadran içi (kenarda yumuşatılmış).
    """
    m = SAAT_BOYUT / 2
    durus = max(plan.durus, 1 / FPS)
    ilerleme = f"(1-pow(1-clip(T/{durus:.4f},0,1),3))"
    dakika = f"({plan.bas_dk}+({plan.fark_dk})*{ilerleme})"
    sure = plan.sure

    def ibre(aci, uzunluk, kalinlik):
        # (dx,dy) noktasının, merkezden aci yönüne (12'den saat yönünde) uzanan çizgiye uzaklığı
        s = f"clip(ld(0)*sin({aci})-ld(1)*cos({aci}),-14,{uzunluk})"
        return f"clip({kalinlik / 2}+0.5-hypot(ld(0)-{s}*sin({aci}),ld(1)+{s}*cos({aci})),0,1)"

    a_yelkovan = f"(2*PI*{dakika}/60)"
    a_akrep = f"(2*PI*{dakika}/720)"
    r = SAAT_YARICAP
    # Çentik: en yakın saat çizgisine açısal uzaklık × yarıçap; 12-3-6-9 daha uzun ve kalın
    aci = "atan2(ld(0),-ld(1))"
    delta = f"(mod({aci}+2*PI+PI/12,PI/6)-PI/12)"
    ceyrek = f"lt(mod(floor(({aci}+2*PI+PI/12)/(PI/6)),3),0.5)"
    ic = f"if({ceyrek},{r - 52},{r - 34})"
    kalin = f"if({ceyrek},5,3)"
    centik = (f"clip({kalin}+0.5-ld(2)*abs({delta}),0,1)"
              f"*clip(ld(2)-{ic}+0.5,0,1)*clip({r - 18}+0.5-ld(2),0,1)")
    cember = f"clip(ld(2)-({r}-{SAAT_KENAR})+0.5,0,1)"
    merkez = "clip(13.5-ld(2),0,1)"
    on = (f"st(0,X+0.5-{m});st(1,Y+0.5-{m});st(2,hypot(ld(0),ld(1)));"
          f"st(5,max(max(max({ibre(a_yelkovan, *SAAT_YELKOVAN)},{ibre(a_akrep, *SAAT_AKREP)}),"
          f"max({centik},{cember})),{merkez}));"
          f"st(6,clip({r}+0.5-ld(2),0,1))")
    (zr, zg, zb), zalfa = SAAT_ZEMIN
    kanallar = [f"{ad}='{on};{z}+({mk}-{z})*ld(5)'"
                for ad, z, mk in (("r", zr, SAAT_MUREKKEP[0]), ("g", zg, SAAT_MUREKKEP[1]),
                                  ("b", zb, SAAT_MUREKKEP[2]))]
    solma = f"clip(T/{SAAT_BELIRME},0,1)*clip(({sure:.4f}-T)/{SAAT_BELIRME},0,1)"
    kanallar.append(f"a='{on};{solma}*ld(6)*({zalfa}+({255 - zalfa})*ld(5))'")
    return (f"color=c=black:s={SAAT_BOYUT}x{SAAT_BOYUT}:r={FPS}:d={sure:.4f},format=rgba,"
            f"geq={':'.join(kanallar)}")


def klip_komutu(gorsel, kare, zoom_bas, zoom_bit, cikti, saat=None):
    """saat: SaatPlani verilirse saat katmanı sahnenin üstüne bindirilir."""
    # Görsel tek kare olarak okunur, bir kez BUYUTME kat büyütülür; zoompan bütün
    # kareleri bu tek kareden üretir (d=kare). Kırpma konumu tam piksele yuvarlandığı
    # için büyütme ne kadar fazlaysa ekrandaki sıçrama o kadar küçük olur (titreme).
    adim = max(kare - 1, 1)
    vf = (f"scale={GEN * BUYUTME}:{YUK * BUYUTME}:flags=lanczos,"
          f"zoompan=z='{zoom_bas}+({zoom_bit - zoom_bas:.4f})*on/{adim}'"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s={GEN}x{YUK}:fps={FPS}")
    if saat is None:
        return ["ffmpeg", "-v", "error", "-y", "-i", gorsel,
                "-vf", vf, "-frames:v", str(kare), *KODLAMA, cikti]
    zincir = (f"[0:v]{vf}[arka];{saat_filtresi(saat)}[saat];"
              f"[arka][saat]overlay={SAAT_X}:{SAAT_Y}:eof_action=pass,format=yuv420p[v]")
    return ["ffmpeg", "-v", "error", "-y", "-i", gorsel, "-filter_complex", zincir,
            "-map", "[v]", "-frames:v", str(kare), *KODLAMA, cikti]


def _kose_mesafesi(yaricap):
    """geq ifadesi: pikselin yuvarlak köşeli dikdörtgen kenarına işaretli uzaklığı → ld(2).
    İçeride negatif, dışarıda pozitif."""
    return (f"st(0,abs(X+0.5-W/2)-(W/2-{yaricap}));st(1,abs(Y+0.5-H/2)-(H/2-{yaricap}));"
            f"st(2,hypot(max(ld(0),0),max(ld(1),0))+min(max(ld(0),ld(1)),0)-{yaricap})")


def kutu_filtresi(gen, yuk, yaricap, zemin, kenar=0, kenar_rgb=KART_VURGU_RGB):
    """Yuvarlak köşeli, yarı saydam (isteğe bağlı kenarlı) kutu üreten tek karelik kaynak."""
    (r, g, b), alfa = zemin
    d = _kose_mesafesi(yaricap)
    kanallar = []
    for ad, ic, dis in (("r", r, kenar_rgb[0]), ("g", g, kenar_rgb[1]), ("b", b, kenar_rgb[2])):
        ifade = f"if(gt(ld(2),-{kenar}),{dis},{ic})" if kenar else str(ic)
        kanallar.append(f"{ad}='{d};{ifade}'")
    a_ic = f"if(gt(ld(2),-{kenar}),255,{alfa})" if kenar else str(alfa)
    kanallar.append(f"a='{d};clip(0.5-ld(2),0,1)*{a_ic}'")
    return f"color=c=black:s={gen}x{yuk}:r=1:d=1,format=rgba,geq={':'.join(kanallar)}"


def gorsel_kose_filtresi(boyut, yaricap):
    """Görseli kare boyuta ölçekleyip köşelerini yuvarlatan filtre zinciri."""
    d = _kose_mesafesi(yaricap)
    return (f"scale={boyut}:{boyut}:flags=lanczos,format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{d};clip(0.5-ld(2),0,1)*255'")


def kart_komutu(arka, plan, kare, cikti, zoom=1.0):
    """Seçim kartı klibi: karartılmış son sahne + yan yana seçenek kartları (sabit kare).

    zoom: son sahne klibinin bittiği zoom; kart aynı kadrajla başlar (sıçrama olmaz).
    Kart tek kare olarak bir kez birleştirilir, sonra `kare` kadar tekrarlanır. Başta son
    sahne karartılmadan görünür; KART_GECIKME'de KART_BELIRME süresince kararma, kutular
    ve görseller birlikte belirir (ASS yazıları da aynı anda). Yazılar burada değil,
    birleştirmede ASS ile basılır.
    """
    gen = round(GEN * zoom / 2) * 2
    yuk = round(YUK * zoom / 2) * 2
    k = KART_KARARTMA
    tekrar = f"loop=loop=-1:size=1,setpts=N/{FPS}/TB"
    zincir = [f"[0:v]scale={gen}:{yuk}:flags=lanczos,crop={GEN}:{YUK},format=rgba,split[arka][kr]",
              f"[kr]colorchannelmixer=rr={k}:gg={k}:bb={k}[z0]"]
    girdiler = ["-i", arka]
    son, n = "z0", 0

    def bindir(kaynak, x, y):
        nonlocal son, n
        n += 1
        zincir.append(f"[{son}][{kaynak}]overlay={x}:{y}[z{n}]")
        son = f"z{n}"

    for i, secenek in enumerate(plan[:len(KART_XLER)]):
        x = KART_XLER[i]
        zincir.append(f"{kutu_filtresi(KART_GEN, KART_YUK, KART_YARICAP, KART_ZEMIN, KART_KENAR)}"
                      f"[k{i}]")
        bindir(f"k{i}", x, KART_Y)
        if secenek.gorsel is not None:
            girdiler += ["-i", str(secenek.gorsel)]
            zincir.append(f"[{len(girdiler) // 2 - 1}:v]"
                          f"{gorsel_kose_filtresi(KART_GORSEL, KART_GORSEL_YARICAP)}[g{i}]")
        else:
            zincir.append(f"{kutu_filtresi(KART_GORSEL, KART_GORSEL, KART_GORSEL_YARICAP, YEDEK_ZEMIN)}"
                          f"[g{i}]")
        bindir(f"g{i}", x + KART_IC_PAY, KART_Y + KART_IC_PAY)
    # Alt katman: karartılmamış son sahne. Üst katman: karartılmış sahne + kartlar; saydamdan
    # belirerek biner. Bölüm 8'de (kart yok) yalnızca kararma olur.
    zincir.append(f"[arka]{tekrar}[a]")
    zincir.append(f"[{son}]{tekrar},fade=t=in:st={KART_GECIKME}:d={KART_BELIRME}:alpha=1[k]")
    zincir.append("[a][k]overlay=0:0,format=yuv420p[v]")
    return ["ffmpeg", "-v", "error", "-y", *girdiler, "-filter_complex", ";".join(zincir),
            "-map", "[v]", "-frames:v", str(kare), *KODLAMA, cikti]


def ses_filtresi(cizelge, ilk_girdi):
    """Cümle seslerini bir sonrakinin başına kadar sessizlikle uzatıp ardına kart sessizliğini
    ekler. Sahne başında es varsa (saat) sessizlik önceki cümleye, ilk sahnedeyse başa eklenir."""
    parcalar, etiketler = [], []
    baslar = [c[2] for c in cizelge.cumleler] + [cizelge.kart_baslangic]
    if baslar[0] > 0:
        parcalar.append(f"anullsrc=r=44100:cl=mono,atrim=duration={baslar[0]:.6f},"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono[bas]")
        etiketler.append("[bas]")
    for k, _c in enumerate(cizelge.cumleler):
        uzunluk = baslar[k + 1] - baslar[k]
        parcalar.append(f"[{ilk_girdi + k}:a]aresample=44100,"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono,"
                        f"apad=whole_dur={uzunluk:.6f},atrim=end={uzunluk:.6f}[a{k}]")
        etiketler.append(f"[a{k}]")
    n = len(cizelge.cumleler)
    kart_sn = cizelge.kart_kare / FPS
    if cizelge.kart_sesli:  # kart okuması cümlelerden sonraki girdi; kart belirince başlar
        parcalar.append(f"anullsrc=r=44100:cl=mono,atrim=duration={KART_SES_BAS:.6f},"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono[kbas]")
        kalan = kart_sn - KART_SES_BAS
        parcalar.append(f"[{ilk_girdi + n}:a]aresample=44100,"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono,"
                        f"apad=whole_dur={kalan:.6f},atrim=end={kalan:.6f}[a{n}]")
        etiketler += ["[kbas]", f"[a{n}]"]
    else:
        parcalar.append(f"anullsrc=r=44100:cl=mono,atrim=duration={kart_sn:.6f},"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono[a{n}]")
        etiketler.append(f"[a{n}]")
    parcalar.append(f"{''.join(etiketler)}concat=n={len(etiketler)}:v=0:a=1[ses]")
    return ";".join(parcalar)


def ambiyans_plani(veri, cizelge, klasor=AMBIYANS_KLASORU):
    """Sahnelerin 'mekan'ından ambiyans parçaları ve uyarılar.

    Ardışık aynı mekânlı sahneler birleşir; son parça kartı da kapsar (kartta söner).
    Mekânı yazılmamış sahne sessiz kalır; dosyası olmayan mekân için uyarı verilir.
    """
    mekanlar = {s["no"]: s.get("mekan") for s in veri["sahneler"]}
    parcalar, uyarilar = [], []
    for no, _gorsel, bas, kare in cizelge.sahneler:
        bit = bas + kare / FPS
        mekan = mekanlar.get(no)
        dosya = Path(klasor) / f"{mekan}.mp3" if mekan else None
        if dosya is not None and not dosya.is_file():
            uyari = f"Ambiyans yok: {_goster(dosya)} ('{mekan}' sahneleri sessiz kalır)."
            if uyari not in uyarilar:
                uyarilar.append(uyari)
            dosya = None
        if dosya is None:
            continue
        if parcalar and parcalar[-1].mekan == mekan and abs(parcalar[-1].bit - bas) < 1e-6:
            parcalar[-1] = parcalar[-1]._replace(bit=bit)
        else:
            parcalar.append(Ambiyans(mekan, dosya, bas, bit))
    if parcalar and abs(parcalar[-1].bit - cizelge.kart_baslangic) < 1e-6:
        parcalar[-1] = parcalar[-1]._replace(bit=cizelge.toplam)
    return parcalar, uyarilar


def ambiyans_filtresi(parcalar, ilk_girdi, toplam):
    """Ambiyans parçalarını yerlerine koyup [amb] (stereo, video boyu) üretir.

    Her girdi döngüyle (-stream_loop -1) açılır; parça dosyanın kendi video zamanındaki
    yerinden kesilir (aynı mekân tekrar gelince baştan başlamasın). Komşu parçalar
    AMBIYANS_GECIS kadar üst üste biner ve çapraz geçer; kartta son parça yavaşça söner.
    """
    if not parcalar:
        return ""
    yari = AMBIYANS_GECIS / 2
    satirlar, etiketler = [], []
    for i, p in enumerate(parcalar):
        bas = max(p.bas - yari, 0.0)
        bit = min(p.bit + yari, toplam)
        uzunluk = bit - bas
        sonme = KART_SURESI if abs(p.bit - toplam) < 1e-6 else AMBIYANS_GECIS
        sonme = min(sonme, uzunluk)
        gecikme = round(bas * 1000)
        satirlar.append(
            f"[{ilk_girdi + i}:a]atrim=start={bas:.6f}:duration={uzunluk:.6f},asetpts=PTS-STARTPTS,"
            f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={AMBIYANS_DB}dB,afade=t=in:st=0:d={min(AMBIYANS_GECIS, uzunluk):.3f},"
            f"afade=t=out:st={uzunluk - sonme:.6f}:d={sonme:.3f},"
            f"adelay=delays={gecikme}:all=1[m{i}]")
        etiketler.append(f"[m{i}]")
    satirlar.append(f"{''.join(etiketler)}amix=inputs={len(etiketler)}:normalize=0:duration=longest,"
                    f"apad=whole_dur={toplam:.6f},atrim=end={toplam:.6f}[amb]")
    return ";".join(satirlar)


def karisim_filtresi():
    """[ses] (anlatım, mono) + [amb] → [son] (stereo). Konuşurken ambiyans kısılır."""
    return ("[ses]aformat=sample_fmts=fltp:channel_layouts=stereo,asplit[ses1][ses2];"
            f"[amb][ses2]{AMBIYANS_KISMA}[ambk];"
            "[ses1][ambk]amix=inputs=2:normalize=0:duration=first[son]")


def birlestirme_komutu(liste, mp3ler, ass, fontlar, filtre_ses, cikti, ambiyanslar=()):
    """Klipleri uç uca ekler, altyazıyı yakar, sesi bağlar. ass/fontlar göreli olmalı
    (Windows'ta 'C:' filtre sözdizimini bozar). ambiyanslar verilirse filtre_ses [amb]'ı da
    üretmeli; girdileri mp3'lerden sonra döngüyle eklenir ve sesle karıştırılır."""
    girdiler = [p for m in mp3ler for p in ("-i", m)]
    girdiler += [p for a in ambiyanslar for p in ("-stream_loop", "-1", "-i", a)]
    filtre = f"[0:v]ass={ass}:fontsdir={fontlar}[v];{filtre_ses}"
    cikis = "[ses]"
    if ambiyanslar:
        filtre += ";" + karisim_filtresi()
        cikis = "[son]"
    return ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste, *girdiler,
            "-filter_complex", filtre,
            "-map", "[v]", "-map", cikis, *KODLAMA, "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", cikti]


def ses_olcum_komutu(girdi):
    """1. geçiş: videonun sesini ölçer (sonuç stderr'de JSON)."""
    return ["ffmpeg", "-hide_banner", "-nostats", "-i", girdi, "-vn",
            "-af", f"{LOUDNORM}:print_format=json", "-f", "null", "-"]


def olcumu_oku(metin):
    """loudnorm'un yazdığı JSON'u okur; ses sessizse (ölçülemezse) None."""
    bas, bit = metin.rfind("{"), metin.rfind("}")
    if bas < 0 or bit < bas:
        return None
    try:
        olcum = json.loads(metin[bas:bit + 1])
        degerler = [float(olcum[k]) for k in ("input_i", "input_tp", "input_lra",
                                               "input_thresh", "target_offset")]
    except (ValueError, KeyError):
        return None
    return olcum if all(math.isfinite(d) for d in degerler) else None


def normallestirme_komutu(girdi, olcum, cikti):
    """2. geçiş: ölçülen değerlerle doğrusal (pompalamasız) normalizasyon; video kopyalanır."""
    filtre = (f"{LOUDNORM}:measured_I={olcum['input_i']}:measured_TP={olcum['input_tp']}"
              f":measured_LRA={olcum['input_lra']}:measured_thresh={olcum['input_thresh']}"
              f":offset={olcum['target_offset']}:linear=true,aresample=44100")
    return ["ffmpeg", "-v", "error", "-y", "-i", girdi, "-map", "0:v", "-map", "0:a",
            "-c:v", "copy", "-af", filtre, "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", cikti]


# --- ffmpeg ile çalıştırma ---

def _program(ad):
    yol = shutil.which(ad)
    if not yol:
        raise MontajHatasi(f"{ad} bulunamadı. Kurulum: KULLANIM.md (Windows: winget install Gyan.FFmpeg).")
    return yol


def _calistir(komut, cwd, ne):
    sonuc = subprocess.run([_program(komut[0]), *komut[1:]], cwd=cwd, capture_output=True,
                           encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        ayrinti = "\n".join(sonuc.stderr.strip().splitlines()[-5:])
        raise MontajHatasi(f"ffmpeg başarısız ({ne}):\n{ayrinti}")


def _olc(komut, cwd):
    """Ölçüm komutunu çalıştırır, stderr'i döndürür."""
    sonuc = subprocess.run([_program(komut[0]), *komut[1:]], cwd=cwd, capture_output=True,
                           encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        ayrinti = "\n".join(sonuc.stderr.strip().splitlines()[-5:])
        raise MontajHatasi(f"ffmpeg başarısız (ses ölçümü):\n{ayrinti}")
    return sonuc.stderr


def ses_suresi(mp3):
    """mp3'ün gerçek süresi (sondaki sessizlik dahil)."""
    sonuc = subprocess.run([_program("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(mp3)],
                           capture_output=True, encoding="utf-8", errors="replace")
    try:
        return float(sonuc.stdout.strip())
    except ValueError:
        raise MontajHatasi(f"Ses okunamadı: {mp3} (bozuk olabilir; ses.py ile yeniden üret).") from None


def _plan_yazdir(cizelge, tam, kart=(), senaryo=""):
    for no, gorsel, bas, kare in cizelge.sahneler:
        adet = sum(1 for c in cizelge.cumleler if c[0].startswith(f"s{no:02d}_"))
        print(f"  Sahne {no:>2}: {gorsel.name:<14} {adet} cümle  {bas:6.2f} sn → {kare / FPS:5.2f} sn")
        if no in cizelge.saatler:
            s = cizelge.saatler[no]
            bit = (s.bas_dk + s.fark_dk) % 1440
            print(f"           saat {s.bas_dk // 60:02d}:{s.bas_dk % 60:02d} → "
                  f"{bit // 60:02d}:{bit % 60:02d} ({'ileri' if s.fark_dk > 0 else 'geri'}), "
                  f"{bas + s.durus:6.2f} sn'de durur")
    print(f"  Kart     : {cizelge.kart_baslangic:6.2f} sn → {cizelge.kart_kare / FPS:5.2f} sn"
          f"{' (anlatıcı okur)' if cizelge.kart_sesli else ' (sessiz)'}")
    for k in kart:
        if k.gorsel is not None:
            print(f"    {k.harf} · {k.metin}: {k.gorsel.name}")
        else:
            print(f"    {k.harf} · {k.metin}: görsel yok, yedek düzen (büyük harf)")
            if k.tarif:
                print(f"    Uyarı: secenek_{k.harf}.png yok. Yerleştir: "
                      f"python kod/gorsel.py {senaryo} --yerlestir secenek{k.harf}")
    print(f"  Toplam   : {cizelge.toplam:.1f} sn")
    if tam and not HEDEF_SURE[0] <= cizelge.toplam <= HEDEF_SURE[1]:
        print(f"  Uyarı: süre hedef aralığın ({HEDEF_SURE[0]}–{HEDEF_SURE[1]} sn) dışında.")


def montajla(veri, klasor, sahneler, varyantlar, kuru=False, sure_olc=ses_suresi,
             ambiyans_klasoru=AMBIYANS_KLASORU):
    """Videoyu üretir ve yolunu döndürür; kuru=True ise yalnızca planı yazar (None)."""
    klasor = Path(klasor)
    tam = list(sahneler) == _sahne_nolari(veri)
    girdiler = girdileri_topla(veri, klasor, sahneler, varyantlar)
    sureler = {c.anahtar: sure_olc(c.mp3) for g in girdiler for c in g.cumleler}
    kart_mp3, kart_uyarisi = kart_sesi(veri, klasor)
    cizelge = zaman_cizelgesi(girdiler, sureler, sure_olc(kart_mp3) if kart_mp3 else None)
    kart = kart_plani(veri["ikilem"], klasor / "gorseller")
    _plan_yazdir(cizelge, tam, kart, _goster(klasor / "senaryo.json"))
    if kart_uyarisi:
        print(f"  Uyarı: {kart_uyarisi}")
    if veri.get("kanca"):
        ek = "" if cizelge.sahneler[0][0] == 1 else " (1. sahne yok, gösterilmez)"
        print(f"  Kanca    : \"{veri['kanca']}\"{ek}")
    ambiyans, uyarilar = ambiyans_plani(veri, cizelge, ambiyans_klasoru)
    for p in ambiyans:
        print(f"  Ambiyans : {p.mekan:<9} {p.bas:6.2f} → {p.bit:6.2f} sn")
    for u in uyarilar:
        print(f"  Uyarı: {u}")
    if kuru:
        return None

    hedef = klasor / ("video.mp4" if tam else "onizleme.mp4")
    with tempfile.TemporaryDirectory(dir=klasor, prefix=".montaj_") as gecici:
        is_ = Path(gecici)
        klipler = []
        for i, (no, gorsel, _bas, kare) in enumerate(cizelge.sahneler):
            zoom = (1.0, ZOOM) if no % 2 else (ZOOM, 1.0)
            ad = f"klip{i:02d}.mp4"
            print(f"  Sahne {no} klibi…")
            _calistir(klip_komutu(str(gorsel.resolve()), kare, *zoom, ad,
                                  saat=cizelge.saatler.get(no)), is_, f"sahne {no}")
            klipler.append(ad)
        son_gorsel = cizelge.sahneler[-1][1]
        kart_mutlak = [k._replace(gorsel=k.gorsel and k.gorsel.resolve()) for k in kart]
        print("  Seçim kartı…")
        _calistir(kart_komutu(str(son_gorsel.resolve()), kart_mutlak, cizelge.kart_kare,
                              "kart.mp4", zoom=zoom[1]), is_, "kart")
        klipler.append("kart.mp4")
        (is_ / "klipler.txt").write_text("".join(f"file '{k}'\n" for k in klipler), encoding="utf-8")
        (is_ / "altyazi.ass").write_text(ass_metni(cizelge, veri["ikilem"], kart, veri.get("kanca")),
                                         encoding="utf-8")
        # Font geçici klasöre kopyalanır: filtreye kısa, göreli, sürücü harfsiz yol verilir.
        (is_ / "fontlar").mkdir()
        font = FONT_KLASORU / FONT_DOSYASI
        if not font.is_file():
            raise MontajHatasi(f"Font bulunamadı: {_goster(font)}")
        shutil.copy2(font, is_ / "fontlar" / FONT_DOSYASI)
        mp3ler = [str(c[1].resolve()) for c in cizelge.cumleler]
        if kart_mp3:
            mp3ler.append(str(kart_mp3.resolve()))
        print("  Birleştiriliyor…")
        filtre_ses = ses_filtresi(cizelge, 1)
        if ambiyans:
            filtre_ses += ";" + ambiyans_filtresi(ambiyans, 1 + len(mp3ler), cizelge.toplam)
        _calistir(birlestirme_komutu("klipler.txt", mp3ler, "altyazi.ass", "fontlar", filtre_ses,
                                     "cikti.mp4", [str(p.dosya.resolve()) for p in ambiyans]),
                  is_, "birleştirme")
        son = "cikti.mp4"
        olcum = olcumu_oku(_olc(ses_olcum_komutu("cikti.mp4"), is_))
        if olcum:
            print(f"  Ses yüksekliği {float(olcum['input_i']):.1f} → -14 LUFS…")
            _calistir(normallestirme_komutu("cikti.mp4", olcum, "cikti_ses.mp4"), is_,
                      "ses yüksekliği")
            son = "cikti_ses.mp4"
        try:
            (is_ / son).replace(hedef)
        except OSError as e:
            raise MontajHatasi(f"{_goster(hedef)} yazılamadı ({e.strerror or e}). Video bir "
                               "oynatıcıda açıksa kapatıp yeniden dene.") from e
    return hedef


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    ayr = argparse.ArgumentParser(description="Bölüm videosunu birleştirir (ffmpeg).")
    ayr.add_argument("senaryo", help="bolumler/bolum_NN/senaryo.json")
    ayr.add_argument("--sahne", help="yalnızca bu sahneler (önizleme): 3 veya 1-3")
    ayr.add_argument("--varyant", help="sahne görsel varyantı (varsayılan a): 3=b,5=c")
    ayr.add_argument("--kuru", action="store_true", help="video üretme, yalnızca planı göster")
    args = ayr.parse_args(argv)
    yol = Path(args.senaryo)
    try:
        veri = senaryo_yukle(yol)
    except SenaryoHatasi as e:
        print("Senaryo geçersiz:")
        for h in e.hatalar:
            print(f"  - {h}")
        return 1
    try:
        sahneler = sahne_secimi(args.sahne, veri)
        varyantlar = varyant_secimi(args.varyant, veri)
        print(f"Bölüm {veri['bolum']}: {veri['baslik']}")
        cikti = montajla(veri, yol.parent, sahneler, varyantlar, kuru=args.kuru)
    except MontajHatasi as e:
        print("Montaj yapılamadı:")
        for h in e.hatalar:
            print(f"  - {h}")
        return 1
    if cikti:
        print(f"✓ {_goster(cikti)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
