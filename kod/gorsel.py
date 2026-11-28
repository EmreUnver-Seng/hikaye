"""Görsel adımı: istekleri hazırlar, elle üretilen görselleri yerleştirir.

Görseller Gemini uygulamasında elle üretilir (Gemini API ücretli olduğu için
kullanılmaz). Bu modül:
  1. Her sahne için hazır istek yazar: eklenecek referans görseller + prompt.
  2. İndirilen görselleri sahne3_a/b/c.png adıyla 1080×1920'ye keserek yerleştirir.
  3. Hangi sahnelerin hazır olduğunu gösterir.
  4. Seçim kartı (ikilem) için seçenek görsellerinin isteğini yazar ve
     secenek_A.png / secenek_B.png olarak 1080×1080 kare yerleştirir.

Kullanım:
    python kod/gorsel.py bolumler/bolum_01/senaryo.json                  # istekler + durum
    python kod/gorsel.py bolumler/bolum_01/senaryo.json --karakter riza  # karakter sayfası isteği
    python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir 3 [dosya ...]
    python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir riza [dosya]
    python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir secenekA [dosya]
    python kod/gorsel.py bolumler/bolum_01/senaryo.json --durum

Dosya verilmezse İndirilenler klasöründeki en yeni görseller önerilir.
Tasarım: docs/superpowers/specs/2026-11-26-gorsel-design.md
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import (KARAKTERLER, SenaryoHatasi, secenek_gorseli,  # noqa: E402
                     secenek_metni, senaryo_yukle)

KOK = Path(__file__).resolve().parent.parent
HARFLER = ("a", "b", "c")
HEDEF_GEN, HEDEF_YUK = 1080, 1920
SECENEK_BOYUT = 1080  # seçim kartı görselleri kare: 1080×1080
SECENEK_HARFLERI = ("A", "B")
ORAN_TOLERANS = 0.10  # 9:16'dan göreli sapma
GORSEL_UZANTILARI = {".png", ".jpg", ".jpeg", ".webp"}

STIL = ("Stil: 2 boyutlu dijital çizgi film illüstrasyonu (yetişkinlere yönelik animasyon "
        "dizisi tarzı). Temiz, koyu renkli kontur çizgileri; iki tonlu hücre gölgelendirme "
        "(cel shading) ile hacim. Saç buklelerinde, yüz hatlarında, kırışıklıklarda, kumaş "
        "kıvrımlarında ve sakal gibi ayrıntılarda orta seviyede detay. Yarı gerçekçi oranlar, "
        "ifadeli yüzler. Fotogerçekçi değil, 3D değil. "
        "Görselde yazı, altyazı, konuşma balonu veya filigran olmasın "
        "(sahne tarifinde açıkça geçen tabela yazısı hariç).")
SAHNE_ISIK = ("Loş, sinematik ışık; mekânın ışık rengi (gece lambası, floresan, sodyum lamba) "
              "karakterlerin üzerine de düşer.")
SAHNE_DERINLIK = (
    "2.5D sahne kompozisyonu: Karakterler 2B çizilir; derinliği mekân taşır. "
    "Mat, hafif hacimli yüzeyler, tutarlı perspektif ve ışıkla ön planı, "
    "karakterlerin bulunduğu orta planı ve arka planı ayır. Sahneye uygunsa "
    "yakındaki bir öğeyle kadrajı çerçevele ve uzak planı hafifçe yumuşat. "
    "Derinlik, sahne tarifindeki hareketi ve bakışları örtmesin."
)
SAHNE_STIL_KIMLIK = "stil-sahne"
STIL_KIMLIK = "stil"  # karakterler/stil.png: yalnızca çizim tarzı örneği


def _stil_satiri(sira):
    return (f"Ekteki {sira}. görsel yalnızca çizim tarzı ve detay seviyesi için örnektir: "
            "içindeki kişiyi, kıyafeti, mekânı ve renkleri kullanma.")

Karakter = namedtuple("Karakter", "ad gorunus")


class GorselHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek hata."""


# --- Tarifler ve prompt ---

def karakter_tarifleri(hikaye_metni):
    """hikaye.md'deki karakter bölümlerinden {kimlik: Karakter} sözlüğü çıkarır.

    Kimlik '- **Referans:** `karakterler/<kimlik>.png`' satırından, görünüş
    '- **Görünüş:**' satırından, ad başlıktaki parantezden önceki kısımdan alınır.
    """
    tarifler = {}
    for bolum in re.split(r"^### ", hikaye_metni, flags=re.MULTILINE)[1:]:
        baslik = bolum.splitlines()[0]
        kimlik = re.search(r"\*\*Referans:\*\*\s*`karakterler/(\w+)\.png`", bolum)
        gorunus = re.search(r"^- \*\*Görünüş:\*\*\s*(.+)$", bolum, flags=re.MULTILINE)
        if kimlik and gorunus:
            ad = baslik.split("(")[0].strip()
            tarifler[kimlik.group(1)] = Karakter(ad, gorunus.group(1).replace("**", "").strip())
    return tarifler


def referans_yolu(kok, kimlik):
    return Path(kok) / "karakterler" / f"{kimlik}.png"


def eksik_referanslar(kimlikler, kok):
    return [k for k in kimlikler if not referans_yolu(kok, k).exists()]


# hikaye.md'de mekân kimliği → ("Mekânlar" maddesinin adı, "Renk paleti" satırının adı)
MEKAN_BASLIKLARI = {
    "otobus": ("Otobüsün içi", "Otobüs içi"),
    "tesis": ("Gece tesisi", "Tesis"),
    "istasyon": ("Benzin istasyonu", "Dış mekân"),
    "dis": (None, "Dış mekân"),
}


def _bolum_metni(hikaye_metni, baslik):
    """'### <baslik>' ile başlayan bölümün metni (bir sonraki ##/### başlığına kadar)."""
    eslesme = re.search(rf"^### {re.escape(baslik)}.*?$(.*?)(?=^#{{2,3}} |\Z)",
                        hikaye_metni, flags=re.MULTILINE | re.DOTALL)
    return eslesme.group(1) if eslesme else ""


def mekan_tarifleri(hikaye_metni):
    """hikaye.md'den {mekan kimliği: tarif} sözlüğü (mekân maddesi + renk paleti satırı)."""
    maddeler = {}
    for ad, tarif in re.findall(r"^\d+\.\s+\*\*(.+?):\*\*\s*(.+)$",
                                _bolum_metni(hikaye_metni, "Mekânlar"), flags=re.MULTILINE):
        # Parantez içleri yazar notudur ("(kurgusal)", "(ipucu olarak kullanılır)"); prompt'a girmez.
        temiz = re.sub(r"\s*\([^)]*\)", "", tarif.replace("**", ""))
        maddeler[ad.split("(")[0].strip()] = temiz.strip()
    paletler = dict(re.findall(r"^- (.+?):\s*(.+)$",
                               _bolum_metni(hikaye_metni, "Renk paleti"), flags=re.MULTILINE))
    tarifler = {}
    for kimlik, (madde, palet) in MEKAN_BASLIKLARI.items():
        parcalar = []
        if madde and madde in maddeler:
            parcalar.append(f"{madde}: {maddeler[madde]}")
        elif not madde:
            parcalar.append("Gece, dış mekân.")
        if palet in paletler:
            parcalar.append(f"Renkler: {paletler[palet].strip()}")
        if len(parcalar) > (0 if madde else 1):
            tarifler[kimlik] = " ".join(parcalar)
    return tarifler


def sahne_promptu(sahne, karakterler, stil_var=False, mekanlar=None, *, sahne_stili=False):
    """Gemini uygulamasına yapıştırılacak sahne prompt'u.

    stil_var: karakterler/stil.png karakter referanslarından sonra en sona eklenecek mi?
    mekanlar: mekan_tarifleri() sonucu; sahnede 'mekan' varsa tarifi eklenir.
    """
    karakter_stili = STIL.replace("Fotogerçekçi değil, 3D değil.",
                                  "Fotogerçekçi görünüm ve 3B karakter renderı kullanma.")
    satirlar = [karakter_stili, SAHNE_DERINLIK, SAHNE_ISIK, "Dikey 9:16 kompozisyon."]
    if sahne["karakterler"]:
        satirlar.append("Karakterler (ekteki referans görsellere birebir uy: yüz, saç, "
                        "kıyafet ve renkler aynı kalsın):")
        for i, kimlik in enumerate(sahne["karakterler"], start=1):
            if kimlik not in karakterler:
                raise GorselHatasi(f"'{kimlik}' karakterinin tarifi hikaye.md'de bulunamadı "
                                   "('### ...' bölümü, 'Görünüş' ve 'Referans' satırları gerekli).")
            k = karakterler[kimlik]
            satirlar.append(f"- Ekteki {i}. görsel: {k.ad} — {k.gorunus}")
    stil_sirasi = len(sahne["karakterler"]) + 1
    if sahne_stili:
        satirlar.append(
            f"Ekteki {stil_sirasi}. görsel sahne derinliği, ışık ve çizim dili örneğidir. "
            "Sahnenin kişilerini, nesnelerini, mekânını ve kadrajını kendi tarifinden al."
        )
    elif stil_var:
        satirlar.append(_stil_satiri(stil_sirasi))
    mekan = sahne.get("mekan")
    if mekan and mekanlar and mekan in mekanlar:
        satirlar.append(f"Mekân: {mekanlar[mekan]}")
    satirlar.append(f"Sahne: {sahne['gorsel']}")
    satirlar.append("Sahne tarifindeki pozlara, hareketlere ve bakış yönüne birebir uy.")
    satirlar.append("Bu sahne için tek bir görsel üret.")
    return "\n".join(satirlar)


def karakter_promptu(karakter, stil_var=False):
    """Karakter referans sayfası prompt'u (beyaz arka plan, boydan)."""
    satirlar = [STIL]
    if stil_var:
        satirlar.append(_stil_satiri(1))
    satirlar += [
        f"Karakter referans sayfası: {karakter.ad}.",
        f"Görünüş: {karakter.gorunus}",
        "Tek figür, boydan, önden, nötr duruş, düz ve nötr ışık. Düz beyaz arka plan, dekor yok.",
        "Bunu 3 farklı görsel olarak, ayrı ayrı üret (3 aday): yüz ifadesi ve duruşta küçük "
        "farklar olsun; görünüş, kıyafet ve renkler aynı kalsın.",
    ]
    return "\n".join(satirlar)


def secenek_promptu(harf, metin, tarif, stil_var=False):
    """Seçim kartındaki seçenek görselinin prompt'u (kare, tek net an/nesne)."""
    satirlar = [STIL, SAHNE_ISIK, "Kare 1:1 kompozisyon."]
    if stil_var:
        satirlar.append(_stil_satiri(1))
    satirlar += [
        f"Bu görsel, bölüm sonundaki seçim kartında '{harf} · {metin}' seçeneğini temsil eder. "
        "Kartta küçük gösterilecek: tek bir ana nesne ya da an, ortada, büyük ve net; "
        "sade, karanlık arka plan; kenarlarda biraz boşluk.",
        f"Görsel: {tarif}",
        "Görselde harf, yazı veya simge olmasın.",
        "Bunu 3 farklı görsel olarak, ayrı ayrı üret: kamera açısı ve kompozisyon farklı olsun.",
    ]
    return "\n".join(satirlar)


def secenek_gorselleri(veri):
    """İkilemdeki {harf: (metin, görsel tarifi)}; tarifi olmayan seçenekler dahil değil."""
    secenekler = veri.get("ikilem", {}).get("secenekler") or {}
    return {h: (secenek_metni(secenekler[h]), secenek_gorseli(secenekler[h]))
            for h in SECENEK_HARFLERI if h in secenekler and secenek_gorseli(secenekler[h])}


# --- Dosya adları ---

def secenek_yolu(klasor, harf):
    return Path(klasor) / f"secenek_{harf}.png"


def secenek_hedefi(metin):
    """'secenekA' / 'secenek_b' gibi --yerlestir hedefi → 'A'; değilse None."""
    eslesme = re.fullmatch(r"secenek_?([abAB])", metin)
    return eslesme.group(1).upper() if eslesme else None


def varyant_yolu(klasor, no, harf):
    return Path(klasor) / f"sahne{no}_{harf}.png"


def hedef_yollar(klasor, no, adet, yeniden):
    """Yerleştirilecek dosyaların hedefleri: boş harfler sırayla; yeniden ise a'dan."""
    if adet > len(HARFLER):
        raise GorselHatasi(f"Bir sahnede en fazla {len(HARFLER)} varyant (a, b, c) olur, "
                           f"{adet} dosya verildi.")
    if yeniden:
        return [varyant_yolu(klasor, no, h) for h in HARFLER[:adet]]
    bos = [varyant_yolu(klasor, no, h) for h in HARFLER
           if not varyant_yolu(klasor, no, h).exists()]
    if len(bos) < adet:
        raise GorselHatasi(f"Sahne {no} için {len(bos)} boş yer var, {adet} dosya verildi. "
                           "Var olanların üzerine yazmak için --yeniden ekle.")
    return bos[:adet]


def oran_uyarisi(gen, yuk, hedef=(HEDEF_GEN, HEDEF_YUK)):
    """Kaynak oranı hedeften (varsayılan 9:16) çok farklıysa uyarı metni, değilse None."""
    sapma = abs((gen / yuk) / (hedef[0] / hedef[1]) - 1)
    if sapma > ORAN_TOLERANS:
        if hedef[0] == hedef[1]:
            oran, istek = "kare (1:1)", "kare (1:1)"
        else:
            oran, istek = "9:16", "dikey (9:16)"
        return (f"kaynak {gen}×{yuk}, {oran} değil; kesimde kenarlardan önemli bir kısım "
                f"kaybolacak. Gerekirse Gemini'den {istek} iste.")
    return None


# --- İstekler ve durum metinleri ---

def _senaryo_komutu(veri):
    return f"python kod/gorsel.py bolumler/bolum_{veri['bolum']:02d}/senaryo.json"


def istekler_metni(veri, karakterler, kok, mekanlar=None):
    """Bölümün tüm sahneleri için markdown istek listesi."""
    komut = _senaryo_komutu(veri)
    satirlar = [
        f"# Bölüm {veri['bolum']}: {veri['baslik']} — görsel istekleri",
        "",
        "Her sahne için: Gemini uygulamasında yeni sohbet aç, referans görselleri sırayla "
        "ekle, prompt'u yapıştır, bir görsel üret ve indir. "
        f"Sonra: `{komut} --yerlestir <sahne no>`",
        "",
    ]
    stil_var = referans_yolu(kok, STIL_KIMLIK).exists()
    sahne_stili = referans_yolu(kok, SAHNE_STIL_KIMLIK).exists()
    for sahne in veri["sahneler"]:
        no = sahne["no"]
        satirlar.append(f"## Sahne {no}")
        eksik = eksik_referanslar(sahne["karakterler"], kok)
        if eksik:
            satirlar.append(f"Referans görseli eksik: {', '.join(eksik)}. Önce karakter sayfası üret:")
            satirlar += [f"- `{komut} --karakter {k}`" for k in eksik]
        else:
            refler = [f"karakterler/{k}.png" for k in sahne["karakterler"]]
            if sahne_stili:
                refler.append(f"karakterler/{SAHNE_STIL_KIMLIK}.png")
            elif stil_var:
                refler.append(f"karakterler/{STIL_KIMLIK}.png")
            satirlar.append(f"Referans: {', '.join(refler) if refler else 'yok'}")
            prompt = sahne_promptu(sahne, karakterler, stil_var, mekanlar, sahne_stili=sahne_stili)
            satirlar += ["```", prompt, "```"]
        satirlar.append("")
    for harf, (metin, tarif) in secenek_gorselleri(veri).items():
        ref = f"karakterler/{STIL_KIMLIK}.png" if stil_var else "yok"
        satirlar.append(f"## Seçim kartı {harf}")
        satirlar.append(f"Referans: {ref}. 3 aday üret, en iyisini indir: "
                        f"`{komut} --yerlestir secenek{harf}`")
        satirlar += ["```", secenek_promptu(harf, metin, tarif, stil_var), "```", ""]
    return "\n".join(satirlar)


def durum_metni(veri, klasor, kok):
    """Sahne başına hazır varyant sayısı ve eksik referanslar."""
    satirlar = []
    for sahne in veri["sahneler"]:
        hazir = [h for h in HARFLER if varyant_yolu(klasor, sahne["no"], h).exists()]
        durum = "hazır" if "a" in hazir else "ana görsel eksik"
        ek = f" ({', '.join(hazir)})" if hazir else ""
        satirlar.append(f"  Sahne {sahne['no']}: {durum}{ek}")
    tarifli = secenek_gorselleri(veri)
    for harf in SECENEK_HARFLERI:
        var = secenek_yolu(klasor, harf).exists()
        if harf in tarifli or var:
            ek = "" if harf in tarifli else " (senaryoda tarif yok)"
            satirlar.append(f"  Seçim kartı {harf}: {'hazır' if var else 'yok'}{ek}")
    kullanilan = sorted({k for s in veri["sahneler"] for k in s["karakterler"]})
    eksik = eksik_referanslar(kullanilan, kok)
    if eksik:
        satirlar.append(f"  Eksik referans görseli: {', '.join(eksik)}")
    return "\n".join(satirlar)


# --- ffmpeg ile yerleştirme ---

def _program(ad):
    yol = shutil.which(ad)
    if not yol:
        raise GorselHatasi(f"{ad} bulunamadı. Kurulum: KULLANIM.md (Windows: winget install Gyan.FFmpeg).")
    return yol


def boyut_oku(dosya):
    """Görselin (genişlik, yükseklik) değeri; okunamazsa GorselHatasi."""
    dosya = Path(dosya)
    if not dosya.is_file():
        raise GorselHatasi(f"Dosya bulunamadı: {dosya}")
    sonuc = subprocess.run(
        [_program("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(dosya)],
        capture_output=True, encoding="utf-8", errors="replace")
    eslesme = re.match(r"(\d+)x(\d+)", sonuc.stdout.strip())
    okunamadi = GorselHatasi(f"Görsel okunamadı: {dosya} (bozuk, yarım inmiş ya da görsel değil).")
    if sonuc.returncode != 0 or not eslesme or "0" in eslesme.groups():
        raise okunamadi
    # ffprobe yalnızca dosyanın başına bakar; yarım inmiş dosyayı yakalamak için tamamını çözdür.
    cozum = subprocess.run([_program("ffmpeg"), "-v", "error", "-i", str(dosya), "-f", "null", "-"],
                           capture_output=True, encoding="utf-8", errors="replace")
    if cozum.returncode != 0 or cozum.stderr.strip():
        raise okunamadi
    return int(eslesme.group(1)), int(eslesme.group(2))


def _donustur(kaynak, hedef, filtre=None):
    """ffmpeg ile PNG'ye çevirir; önce geçici dosyaya yazar, başarılıysa yerine koyar."""
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.stem + ".gecici.png")
    komut = [_program("ffmpeg"), "-v", "error", "-y", "-i", str(kaynak)]
    if filtre:
        komut += ["-vf", filtre]
    komut += ["-frames:v", "1", str(gecici)]
    sonuc = subprocess.run(komut, capture_output=True, encoding="utf-8", errors="replace")
    if sonuc.returncode != 0 or not gecici.exists():
        gecici.unlink(missing_ok=True)
        ayrinti = "\n".join(sonuc.stderr.strip().splitlines()[:3])
        raise GorselHatasi(f"ffmpeg dönüştüremedi: {kaynak}\n{ayrinti}")
    gecici.replace(hedef)


def sahneye_yerlestir(kaynak, hedef):
    """Kaynağı 1080×1920'ye ölçekleyip ortadan keser. Oran uyarısını (veya None) döndürür."""
    gen, yuk = boyut_oku(kaynak)
    _donustur(kaynak, hedef,
              f"scale={HEDEF_GEN}:{HEDEF_YUK}:force_original_aspect_ratio=increase,"
              f"crop={HEDEF_GEN}:{HEDEF_YUK}")
    return oran_uyarisi(gen, yuk)


def secenege_yerlestir(kaynak, hedef):
    """Kaynağı 1080×1080'e ölçekleyip ortadan keser. Oran uyarısını (veya None) döndürür."""
    gen, yuk = boyut_oku(kaynak)
    _donustur(kaynak, hedef,
              f"scale={SECENEK_BOYUT}:{SECENEK_BOYUT}:force_original_aspect_ratio=increase,"
              f"crop={SECENEK_BOYUT}:{SECENEK_BOYUT}")
    return oran_uyarisi(gen, yuk, (SECENEK_BOYUT, SECENEK_BOYUT))


def karaktere_yerlestir(kaynak, hedef):
    """Karakter referansını kesmeden PNG'ye çevirir."""
    boyut_oku(kaynak)
    _donustur(kaynak, hedef)


def en_yeni_gorseller(klasor, adet):
    """Klasördeki en yeni `adet` görsel (yeniden eskiye)."""
    klasor = Path(klasor)
    if not klasor.is_dir():
        raise GorselHatasi(f"Klasör bulunamadı: {klasor}. Dosyaları komutta ver.")
    gorseller = [p for p in klasor.iterdir()
                 if p.is_file() and p.suffix.lower() in GORSEL_UZANTILARI]
    gorseller.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(gorseller) < adet:
        raise GorselHatasi(f"{klasor} içinde {adet} görsel gerekiyordu, {len(gorseller)} bulundu.")
    return gorseller[:adet]


# --- Komut satırı ---

def _dosyalari_sec(dosyalar, adet):
    """Verilen dosyalar ya da İndirilenler'deki en yeniler (onayla)."""
    if dosyalar:
        return [Path(d) for d in dosyalar]
    secilen = en_yeni_gorseller(Path.home() / "Downloads", adet)
    print("İndirilenler'deki en yeni görseller:")
    for d in secilen:
        print(f"  - {d.name}")
    if input("Bunlar yerleştirilsin mi? (e/h) ").strip().lower() not in ("e", "evet"):
        raise GorselHatasi("Vazgeçildi, hiçbir dosya yerleştirilmedi.")
    return secilen


def _sahneye(veri, gorseller, no, dosyalar, yeniden):
    if not 1 <= no <= len(veri["sahneler"]):
        raise GorselHatasi(f"Sahne {no} yok; bu bölümde 1–{len(veri['sahneler'])} arası sahne var.")
    adet = len(dosyalar) if dosyalar else 1
    hedefler = hedef_yollar(gorseller, no, adet, yeniden)
    kaynaklar = _dosyalari_sec(dosyalar, adet)
    for kaynak in kaynaklar:  # hiçbir şey yazmadan önce hepsini kontrol et
        boyut_oku(kaynak)
    for kaynak, hedef in zip(kaynaklar, hedefler):
        uyari = sahneye_yerlestir(kaynak, hedef)
        print(f"✓ {kaynak.name} → {hedef.relative_to(KOK) if hedef.is_relative_to(KOK) else hedef}")
        if uyari:
            print(f"  ! {uyari}")


def _karaktere(kimlik, dosyalar, yeniden):
    if len(dosyalar) > 1:
        raise GorselHatasi("Karakter referansı için tek dosya ver.")
    hedef = referans_yolu(KOK, kimlik)
    if hedef.exists() and not yeniden:
        raise GorselHatasi(f"karakterler/{kimlik}.png zaten var. Değiştirmek için --yeniden ekle.")
    kaynak = _dosyalari_sec(dosyalar, 1)[0]
    karaktere_yerlestir(kaynak, hedef)
    print(f"✓ {kaynak.name} → karakterler/{kimlik}.png")


def _secenege(veri, gorseller, harf, dosyalar, yeniden):
    if len(dosyalar) > 1:
        raise GorselHatasi(f"Seçim kartı {harf} için tek dosya ver (en iyi adayı).")
    if harf not in (veri.get("ikilem", {}).get("secenekler") or {}):
        raise GorselHatasi(f"Bu bölümün ikileminde {harf} seçeneği yok.")
    hedef = secenek_yolu(gorseller, harf)
    if hedef.exists() and not yeniden:
        raise GorselHatasi(f"{hedef.name} zaten var. Değiştirmek için --yeniden ekle.")
    kaynak = _dosyalari_sec(dosyalar, 1)[0]
    uyari = secenege_yerlestir(kaynak, hedef)
    print(f"✓ {kaynak.name} → {hedef.relative_to(KOK) if hedef.is_relative_to(KOK) else hedef}")
    if uyari:
        print(f"  ! {uyari}")
    if harf not in secenek_gorselleri(veri):
        print(f"  ! Senaryoda {harf} seçeneğinin görsel tarifi yok; montaj yine de bu görseli kullanır.")


def main(argv):
    ayristirici = argparse.ArgumentParser(
        prog="gorsel.py", description="Görsel istekleri hazırlar ve görselleri yerleştirir.")
    ayristirici.add_argument("senaryo", help="bolumler/bolum_NN/senaryo.json")
    grup = ayristirici.add_mutually_exclusive_group()
    grup.add_argument("--karakter", metavar="KIMLIK", help="karakter sayfası isteğini göster")
    grup.add_argument("--yerlestir", nargs="+", metavar=("HEDEF", "DOSYA"),
                      help="sahne numarası, karakter kimliği ya da secenekA/secenekB, "
                           "ardından dosyalar")
    grup.add_argument("--durum", action="store_true", help="hazır görselleri göster")
    ayristirici.add_argument("--yeniden", action="store_true",
                             help="var olan görsellerin üzerine yaz")
    args = ayristirici.parse_args(argv)

    senaryo = Path(args.senaryo)
    try:
        veri = senaryo_yukle(senaryo)
    except SenaryoHatasi as e:
        print(f"✗ {senaryo} geçersiz ({len(e.hatalar)} hata):")
        for h in e.hatalar:
            print(f"  - {h}")
        return 1
    gorseller = senaryo.parent / "gorseller"

    try:
        if args.yerlestir:
            hedef, dosyalar = args.yerlestir[0], args.yerlestir[1:]
            if hedef.isascii() and hedef.isdecimal():
                _sahneye(veri, gorseller, int(hedef), dosyalar, args.yeniden)
            elif secenek_hedefi(hedef):
                _secenege(veri, gorseller, secenek_hedefi(hedef), dosyalar, args.yeniden)
            elif hedef in KARAKTERLER or hedef == STIL_KIMLIK:
                _karaktere(hedef, dosyalar, args.yeniden)
            else:
                raise GorselHatasi(f"Bilinmeyen hedef '{hedef}': sahne numarası, karakter "
                                   f"kimliği ({', '.join(KARAKTERLER)}), '{STIL_KIMLIK}' "
                                   "ya da secenekA/secenekB olmalı.")
            return 0
        if args.durum:
            print(f"Bölüm {veri['bolum']} görselleri ({gorseller}):")
            print(durum_metni(veri, gorseller, KOK))
            return 0

        hikaye = KOK / "hikaye.md"
        if not hikaye.exists():
            raise GorselHatasi(f"hikaye.md bulunamadı: {hikaye}")
        hikaye_metni = hikaye.read_text(encoding="utf-8")
        tarifler = karakter_tarifleri(hikaye_metni)
        if args.karakter:
            if args.karakter not in tarifler:
                raise GorselHatasi(f"'{args.karakter}' tarifi hikaye.md'de yok. "
                                   f"Kimlikler: {', '.join(sorted(tarifler))}.")
            stil_var = referans_yolu(KOK, STIL_KIMLIK).exists()
            ek = f" karakterler/{STIL_KIMLIK}.png dosyasını ekle," if stil_var else ""
            print(f"Gemini uygulamasında yeni sohbet aç,{ek} bu prompt'u yapıştır, 3 aday üret:\n")
            print(karakter_promptu(tarifler[args.karakter], stil_var))
            print(f"\nBeğendiğini indir, sonra: {_senaryo_komutu(veri)} "
                  f"--yerlestir {args.karakter} [dosya]")
            return 0

        metin = istekler_metni(veri, tarifler, KOK, mekan_tarifleri(hikaye_metni))
        gorseller.mkdir(parents=True, exist_ok=True)
        (gorseller / "istekler.md").write_text(metin, encoding="utf-8")
        print(metin)
        print(f"Kaydedildi: {gorseller / 'istekler.md'}\n")
        print("Durum:")
        print(durum_metni(veri, gorseller, KOK))
        return 0
    except GorselHatasi as e:
        print(f"✗ {e}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\n✗ Vazgeçildi, hiçbir dosya yerleştirilmedi.")
        return 1
    except OSError as e:
        print(f"✗ Dosya işlemi başarısız: {e.filename or ''} ({e.strerror or e}). "
              "Dosya başka bir programda açık ya da klasöre erişim izni yok olabilir.")
        return 1


if __name__ == "__main__":
    # Windows konsolunda Türkçe karakterler ve ✓ işareti bozulmasın.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
