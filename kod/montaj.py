"""Montaj adımı: görselleri, cümle seslerini ve altyazıyı dikey videoda birleştirir.

Her sahne yavaş zoom'lu bir klip olur; cümle sesleri arka arkaya dizilir; o an
söylenen kelimesi vurgulu altyazı ve sonda ikilem (seçenek) kartı eklenir.
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
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import SenaryoHatasi, secenek_gorseli, secenek_metni, senaryo_yukle  # noqa: E402
from ses import SesHatasi, dosya_adi, kayitlari_yukle  # noqa: E402

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
KART_SATIR = 14                      # kart metninde satır başına en fazla karakter
SORU_ALT_Y = 700                     # soru bu çizgiye alttan dayanır (yukarı doğru büyür)
CAGRI_Y = KART_Y + KART_YUK + 90
SECENEK_HARFLERI = ("A", "B")

KODLAMA = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", str(FPS)]

CumleGirdisi = namedtuple("CumleGirdisi", "anahtar mp3 kelimeler")
SahneGirdisi = namedtuple("SahneGirdisi", "no gorsel cumleler")
# sahneler: (no, gorsel, baslangic, kare); cumleler: (anahtar, mp3, baslangic, slot_bitis, kelimeler)
Cizelge = namedtuple("Cizelge", "sahneler cumleler kart_baslangic kart_kare toplam")
# Seçim kartındaki bir seçenek: gorsel = secenek_X.png yolu ya da None (yedek düzen);
# tarif = senaryodaki görsel tarifi var mı (yoksa eksik görsel için uyarı verilmez).
KartSecenegi = namedtuple("KartSecenegi", "harf metin gorsel tarif")


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
        girdiler.append(SahneGirdisi(no, gorsel, cumleler))
    if hatalar:
        raise MontajHatasi(hatalar)
    return girdiler


# --- Zaman çizelgesi ---

def zaman_cizelgesi(girdiler, sureler):
    """Sahne ve cümlelerin video üzerindeki yerleri.

    Sahne süresi kareye yuvarlanır; sahne başlangıçları önceki karelerin
    toplamından hesaplanır, böylece ses ile görüntü arasında kayma birikmez.
    """
    sahneler, cumleler = [], []
    kare_toplam = 0
    for g in girdiler:
        bas = kare_toplam / FPS
        ofsetler, t = [], 0.0
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
        kare_toplam += kare
    kart_kare = round(KART_SURESI * FPS)
    kart_bas = kare_toplam / FPS
    return Cizelge(sahneler, cumleler, kart_bas, kart_kare, (kare_toplam + kart_kare) / FPS)


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
        metin = "\\N".join(ass_kacir(satir) for satir in satirlara_bol(k.metin))
        if k.gorsel is None:  # yedek düzen: görselin yerinde büyük harf, altta yalnızca metin
            orta = KART_Y + KART_IC_PAY + KART_GORSEL // 2
            olaylar.append(_olay(gec, bitis, "Harf",
                                 f"{{\\an5\\pos({x},{orta}){_FAD}\\c{VURGU}}}{k.harf}"))
            olaylar.append(_olay(gec, bitis, "Kart",
                                 f"{{\\an8\\pos({x},{KART_METIN_Y + 20}){_FAD}}}{metin}"))
        else:
            olaylar.append(_olay(
                gec, bitis, "Kart",
                f"{{\\an8\\pos({x},{KART_METIN_Y}){_FAD}}}"
                f"{{\\fs76\\c{VURGU}}}{k.harf}{{\\fs48\\c{BEYAZ}}}\\N{metin}"))
    cagri = "Yorumlara A ya da B yaz" if plan else "Yorumlara yaz"
    y = CAGRI_Y if plan else 1100
    olaylar.append(_olay(gec, bitis, "Not", f"{{\\an5\\pos(540,{y}){_FAD}}}{cagri}"))
    return olaylar


def ass_metni(cizelge, ikilem, plan=None):
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
    ]
    olaylar = altyazi_olaylari(cizelge) + kart_olaylari(
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

def klip_komutu(gorsel, kare, zoom_bas, zoom_bit, cikti):
    # Görsel tek kare olarak okunur, bir kez BUYUTME kat büyütülür; zoompan bütün
    # kareleri bu tek kareden üretir (d=kare). Kırpma konumu tam piksele yuvarlandığı
    # için büyütme ne kadar fazlaysa ekrandaki sıçrama o kadar küçük olur (titreme).
    adim = max(kare - 1, 1)
    vf = (f"scale={GEN * BUYUTME}:{YUK * BUYUTME}:flags=lanczos,"
          f"zoompan=z='{zoom_bas}+({zoom_bit - zoom_bas:.4f})*on/{adim}'"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s={GEN}x{YUK}:fps={FPS}")
    return ["ffmpeg", "-v", "error", "-y", "-i", gorsel,
            "-vf", vf, "-frames:v", str(kare), *KODLAMA, cikti]


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
    """Cümle seslerini slotlarına göre sessizlikle uzatıp ardına kart sessizliğini ekler."""
    parcalar, etiketler = [], []
    for k, (_a, _m, bas, slot, _k) in enumerate(cizelge.cumleler):
        uzunluk = slot - bas
        parcalar.append(f"[{ilk_girdi + k}:a]aresample=44100,"
                        f"aformat=sample_fmts=fltp:channel_layouts=mono,"
                        f"apad=whole_dur={uzunluk:.6f},atrim=end={uzunluk:.6f}[a{k}]")
        etiketler.append(f"[a{k}]")
    n = len(cizelge.cumleler)
    parcalar.append(f"anullsrc=r=44100:cl=mono,atrim=duration={cizelge.kart_kare / FPS:.6f},"
                    f"aformat=sample_fmts=fltp:channel_layouts=mono[a{n}]")
    etiketler.append(f"[a{n}]")
    parcalar.append(f"{''.join(etiketler)}concat=n={n + 1}:v=0:a=1[ses]")
    return ";".join(parcalar)


def birlestirme_komutu(liste, mp3ler, ass, fontlar, filtre_ses, cikti):
    """Klipleri uç uca ekler, altyazıyı yakar, sesi bağlar. ass/fontlar göreli olmalı
    (Windows'ta 'C:' filtre sözdizimini bozar)."""
    girdiler = [p for m in mp3ler for p in ("-i", m)]
    return ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste, *girdiler,
            "-filter_complex", f"[0:v]ass={ass}:fontsdir={fontlar}[v];{filtre_ses}",
            "-map", "[v]", "-map", "[ses]", *KODLAMA, "-c:a", "aac", "-b:a", "192k",
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
    print(f"  Kart     : {cizelge.kart_baslangic:6.2f} sn → {cizelge.kart_kare / FPS:5.2f} sn")
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


def montajla(veri, klasor, sahneler, varyantlar, kuru=False, sure_olc=ses_suresi):
    """Videoyu üretir ve yolunu döndürür; kuru=True ise yalnızca planı yazar (None)."""
    klasor = Path(klasor)
    tam = list(sahneler) == _sahne_nolari(veri)
    girdiler = girdileri_topla(veri, klasor, sahneler, varyantlar)
    sureler = {c.anahtar: sure_olc(c.mp3) for g in girdiler for c in g.cumleler}
    cizelge = zaman_cizelgesi(girdiler, sureler)
    kart = kart_plani(veri["ikilem"], klasor / "gorseller")
    _plan_yazdir(cizelge, tam, kart, _goster(klasor / "senaryo.json"))
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
            _calistir(klip_komutu(str(gorsel.resolve()), kare, *zoom, ad), is_, f"sahne {no}")
            klipler.append(ad)
        son_gorsel = cizelge.sahneler[-1][1]
        kart_mutlak = [k._replace(gorsel=k.gorsel and k.gorsel.resolve()) for k in kart]
        print("  Seçim kartı…")
        _calistir(kart_komutu(str(son_gorsel.resolve()), kart_mutlak, cizelge.kart_kare,
                              "kart.mp4", zoom=zoom[1]), is_, "kart")
        klipler.append("kart.mp4")
        (is_ / "klipler.txt").write_text("".join(f"file '{k}'\n" for k in klipler), encoding="utf-8")
        (is_ / "altyazi.ass").write_text(ass_metni(cizelge, veri["ikilem"], kart), encoding="utf-8")
        # Font geçici klasöre kopyalanır: filtreye kısa, göreli, sürücü harfsiz yol verilir.
        (is_ / "fontlar").mkdir()
        font = FONT_KLASORU / FONT_DOSYASI
        if not font.is_file():
            raise MontajHatasi(f"Font bulunamadı: {_goster(font)}")
        shutil.copy2(font, is_ / "fontlar" / FONT_DOSYASI)
        mp3ler = [str(c[1].resolve()) for c in cizelge.cumleler]
        print("  Birleştiriliyor…")
        _calistir(birlestirme_komutu("klipler.txt", mp3ler, "altyazi.ass", "fontlar",
                                     ses_filtresi(cizelge, 1), "cikti.mp4"), is_, "birleştirme")
        try:
            (is_ / "cikti.mp4").replace(hedef)
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
