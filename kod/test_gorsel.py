"""gorsel.py için testler.

Çalıştırma:  python kod/test_gorsel.py
Ek kütüphane gerekmez. ffmpeg'li testler ffmpeg yoksa atlanır.
Gemini veya başka bir ağ servisine bağlanmaz.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOD = Path(__file__).resolve().parent
KOK = KOD.parent
sys.path.insert(0, str(KOD))

from gorsel import (  # noqa: E402
    GorselHatasi,
    Karakter,
    boyut_oku,
    durum_metni,
    en_yeni_gorseller,
    hedef_yollar,
    istekler_metni,
    karakter_promptu,
    karakter_tarifleri,
    mekan_tarifleri,
    karaktere_yerlestir,
    oran_uyarisi,
    sahne_promptu,
    sahneye_yerlestir,
    secenek_gorselleri,
    secenek_hedefi,
    secenek_promptu,
    secenek_yolu,
    secenege_yerlestir,
    varyant_yolu,
    _sahneye,
)

HIKAYE = (KOK / "hikaye.md").read_text(encoding="utf-8")
FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def hata_bekle(fonksiyon, parca=""):
    try:
        fonksiyon()
    except GorselHatasi as e:
        assert parca in str(e), f"'{parca}' hata mesajında yok: {e}"
        return
    raise AssertionError("GorselHatasi fırlatılmadı")


def ornek_sahne(no=1, karakterler=("sen", "nadide")):
    return {"no": no, "gorsel": f"Sahne {no}: otobüsün içi, mor-mavi gece ışığı.",
            "karakterler": list(karakterler),
            "cumleler": [{"konusan": "anlatici", "metin": "Gece."}]}


def ornek_veri():
    sahneler = [ornek_sahne(1, ["sen"]), ornek_sahne(2, ["sen", "nadide"]),
                ornek_sahne(3, [])]
    return {"bolum": 1, "baslik": "Kalkış", "sahneler": sahneler,
            "ikilem": {"soru": "?", "secenekler": {"A": "a", "B": "b"}}}


def bos_dosya(yol):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(b"x")


def png_uret(yol, gen, yuk):
    """ffmpeg ile düz renkli bir test görseli üretir."""
    subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"color=c=red:s={gen}x{yuk}", "-frames:v", "1", str(yol)],
                   check=True)


# --- Görev 1: saf kısım ---

def test_tarifler_hikaye_mdden():
    t = karakter_tarifleri(HIKAYE)
    assert set(t) == {"sen", "nadide", "riza", "kerem", "murat", "ayla"}, set(t)
    assert t["riza"].ad == "Rıza Usta", t["riza"].ad
    assert "bıyık" in t["riza"].gorunus
    assert "Hardal sarısı" in t["sen"].gorunus  # ** işaretleri temizlenmiş
    assert "**" not in t["sen"].gorunus


def test_eksik_karakter_bolumu():
    bas = HIKAYE.index("### Ayla")
    son = HIKAYE.index("### Renk özeti")
    t = karakter_tarifleri(HIKAYE[:bas] + HIKAYE[son:])
    assert "ayla" not in t
    hata_bekle(lambda: sahne_promptu(ornek_sahne(1, ["ayla"]), t), "ayla")


def test_sahne_promptu():
    t = karakter_tarifleri(HIKAYE)
    p = sahne_promptu(ornek_sahne(1, ["nadide", "sen"]), t)
    for parca in ("kontur", "9:16", "konuşma balonu", "Sahne 1: otobüsün içi"):
        assert parca in p, f"'{parca}' prompt'ta yok"
    assert p.index("1. görsel: Nadide Teyze") < p.index("2. görsel: Sen")


def test_sahne_promptu_karaktersiz():
    p = sahne_promptu(ornek_sahne(1, []), karakter_tarifleri(HIKAYE))
    assert "görsel:" not in p
    assert "Sahne 1" in p


def test_karakter_promptu():
    t = karakter_tarifleri(HIKAYE)
    p = karakter_promptu(t["kerem"])
    assert "beyaz" in p and "kontur" in p and "Kerem" in p
    assert "kırmızı" in p.lower()


def test_varyant_yolu():
    assert varyant_yolu(Path("g"), 3, "b") == Path("g") / "sahne3_b.png"


def test_hedef_yollar_bos_harfler():
    with tempfile.TemporaryDirectory() as d:
        k = Path(d)
        bos_dosya(varyant_yolu(k, 2, "a"))
        assert hedef_yollar(k, 2, 2, False) == [varyant_yolu(k, 2, "b"), varyant_yolu(k, 2, "c")]


def test_hedef_yollar_dolu_hata():
    with tempfile.TemporaryDirectory() as d:
        k = Path(d)
        for h in "abc":
            bos_dosya(varyant_yolu(k, 2, h))
        hata_bekle(lambda: hedef_yollar(k, 2, 1, False), "--yeniden")
        hata_bekle(lambda: hedef_yollar(k, 2, 4, True), "3")


def test_hedef_yollar_yeniden():
    with tempfile.TemporaryDirectory() as d:
        k = Path(d)
        for h in "abc":
            bos_dosya(varyant_yolu(k, 2, h))
        assert hedef_yollar(k, 2, 2, True) == [varyant_yolu(k, 2, "a"), varyant_yolu(k, 2, "b")]


def test_oran_uyarisi():
    assert oran_uyarisi(1080, 1920) is None
    assert oran_uyarisi(1000, 1800) is None
    assert oran_uyarisi(768, 1344) is None
    assert oran_uyarisi(1024, 1024) is not None
    assert "1024×1024" in oran_uyarisi(1024, 1024)


def test_istekler_eksik_referans():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        bos_dosya(kok / "karakterler" / "sen.png")
        metin = istekler_metni(ornek_veri(), karakter_tarifleri(HIKAYE), kok)
        s1 = metin[metin.index("## Sahne 1"):metin.index("## Sahne 2")]
        s2 = metin[metin.index("## Sahne 2"):metin.index("## Sahne 3")]
        s3 = metin[metin.index("## Sahne 3"):]
        assert "```" in s1 and "karakterler/sen.png" in s1
        assert "--karakter nadide" in s2 and "```" not in s2
        assert "```" in s3 and "Referans: yok" in s3


def test_durum_metni():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        g = kok / "gorseller"
        bos_dosya(varyant_yolu(g, 1, "a"))
        bos_dosya(varyant_yolu(g, 1, "c"))
        metin = durum_metni(ornek_veri(), g, kok)
        assert "Sahne 1: 2/3" in metin, metin
        assert "Sahne 3: 0/3" in metin, metin
        assert "sen" in metin and "nadide" in metin  # eksik referanslar


# --- Görev 2: yerleştirme ve komut satırı ---

def test_sahneye_yerlestir_boyut():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        kaynak, hedef = Path(d) / "kare.png", Path(d) / "g" / "sahne1_a.png"
        png_uret(kaynak, 1024, 1024)
        uyari = sahneye_yerlestir(kaynak, hedef)
        assert boyut_oku(hedef) == (1080, 1920)
        assert uyari is not None


def test_karaktere_yerlestir_kesmez():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        kaynak, hedef = Path(d) / "k.jpg", Path(d) / "karakterler" / "sen.png"
        png_uret(kaynak, 600, 900)
        karaktere_yerlestir(kaynak, hedef)
        assert boyut_oku(hedef) == (600, 900)
        assert hedef.read_bytes()[:4] == b"\x89PNG"


def test_bozuk_kaynak():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        kaynak, hedef = Path(d) / "bozuk.png", Path(d) / "sahne1_a.png"
        kaynak.write_text("görsel değil", encoding="utf-8")
        hata_bekle(lambda: sahneye_yerlestir(kaynak, hedef), "bozuk.png")
        assert not hedef.exists()
        hata_bekle(lambda: sahneye_yerlestir(Path(d) / "yok.png", hedef), "yok.png")


def test_en_yeni_gorseller():
    with tempfile.TemporaryDirectory() as d:
        k = Path(d)
        simdi = time.time()
        for i, ad in enumerate(["eski.png", "orta.jpg", "yeni.webp", "not.txt"]):
            bos_dosya(k / ad)
            os.utime(k / ad, (simdi + i, simdi + i))
        assert en_yeni_gorseller(k, 2) == [k / "yeni.webp", k / "orta.jpg"]
        hata_bekle(lambda: en_yeni_gorseller(k, 4), "3")


def test_cli_durum():
    sonuc = subprocess.run(
        [sys.executable, str(KOD / "gorsel.py"), str(KOK / "bolumler" / "bolum_01" / "senaryo.json"),
         "--durum"], capture_output=True, encoding="utf-8", errors="replace")
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    assert "Sahne 1" in sonuc.stdout, sonuc.stdout


def test_cli_yanlis_hedef():
    sonuc = subprocess.run(
        [sys.executable, str(KOD / "gorsel.py"), str(KOK / "bolumler" / "bolum_01" / "senaryo.json"),
         "--yerlestir", "hayalet", "x.png"], capture_output=True, encoding="utf-8", errors="replace")
    assert sonuc.returncode == 1
    assert "hayalet" in sonuc.stdout, sonuc.stdout


def test_boyut_oku_gorsel_olmayan():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        metin = Path(d) / "metin.png"
        metin.write_text("görsel değil", encoding="utf-8")
        hata_bekle(lambda: boyut_oku(metin), "metin.png")


def test_boyut_oku_yarim_inmis():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        tam, yarim = Path(d) / "tam.png", Path(d) / "yarim.png"
        png_uret(tam, 1080, 1920)
        veri = tam.read_bytes()
        yarim.write_bytes(veri[: len(veri) // 2])
        hata_bekle(lambda: boyut_oku(yarim), "yarim.png")


def test_ikinci_dosya_bozuksa_hicbir_sey_yazilmaz():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        k = Path(d)
        iyi, bozuk = k / "iyi.png", k / "bozuk.png"
        png_uret(iyi, 1080, 1920)
        veri = iyi.read_bytes()
        bozuk.write_bytes(veri[: len(veri) // 2])
        g = k / "gorseller"
        hata_bekle(lambda: _sahneye(ornek_veri(), g, 1, [str(iyi), str(bozuk)], False), "bozuk.png")
        assert not list(g.glob("sahne1_*")), list(g.glob("sahne1_*"))


def test_cli_rakam_olmayan_sayi():
    sonuc = subprocess.run(
        [sys.executable, str(KOD / "gorsel.py"), str(KOK / "bolumler" / "bolum_01" / "senaryo.json"),
         "--yerlestir", "³", "x.png"], capture_output=True, encoding="utf-8", errors="replace")
    assert sonuc.returncode == 1
    assert "Traceback" not in sonuc.stderr, sonuc.stderr


def test_cli_onay_sorusunda_girdi_yok():
    """stdin kapalıyken (EOF) traceback değil Türkçe hata."""
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        ev = Path(d)
        (ev / "Downloads").mkdir()
        for i in range(3):
            png_uret(ev / "Downloads" / f"g{i}.png", 1080, 1920)
        ortam = dict(os.environ, USERPROFILE=str(ev), HOME=str(ev))
        sonuc = subprocess.run(
            [sys.executable, str(KOD / "gorsel.py"),
             str(KOK / "bolumler" / "bolum_01" / "senaryo.json"), "--yerlestir", "8"],
            capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=ortam)
        assert sonuc.returncode == 1, sonuc.stdout
        assert "Traceback" not in sonuc.stderr, sonuc.stderr
        assert "✗" in sonuc.stdout, sonuc.stdout


# --- Stil referansı (karakterler/stil.png) ---

def test_sahne_promptu_stil_referansi():
    t = karakter_tarifleri(HIKAYE)
    p = sahne_promptu(ornek_sahne(1, ["sen", "nadide"]), t, stil_var=True)
    assert "Ekteki 3. görsel" in p and "yalnızca çizim tarzı" in p, p
    assert "kişiyi" in p  # stil görselindeki kişiyi kopyalama uyarısı
    p0 = sahne_promptu(ornek_sahne(1, []), t, stil_var=True)
    assert "Ekteki 1. görsel" in p0 and "yalnızca çizim tarzı" in p0


def test_sahne_promptu_stilsiz():
    p = sahne_promptu(ornek_sahne(1, ["sen"]), karakter_tarifleri(HIKAYE))
    assert "çizim tarzı" not in p


def test_karakter_promptu_stil_referansi():
    k = karakter_tarifleri(HIKAYE)["sen"]
    assert "Ekteki 1. görsel" in karakter_promptu(k, stil_var=True)
    assert "Ekteki" not in karakter_promptu(k)


def test_stil_metni_detay_seviyesi():
    p = karakter_promptu(karakter_tarifleri(HIKAYE)["sen"])
    for parca in ("gölgelendirme", "detay", "fotogerçekçi değil"):
        assert parca in p.lower(), f"'{parca}' stil metninde yok"


def test_istekler_stil_referansi_sona_eklenir():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        bos_dosya(kok / "karakterler" / "sen.png")
        bos_dosya(kok / "karakterler" / "stil.png")
        metin = istekler_metni(ornek_veri(), karakter_tarifleri(HIKAYE), kok)
        s1 = metin[metin.index("## Sahne 1"):metin.index("## Sahne 2")]
        s3 = metin[metin.index("## Sahne 3"):]
        assert "karakterler/sen.png, karakterler/stil.png" in s1, s1
        assert "Referans: karakterler/stil.png" in s3, s3


def test_cli_stil_yerlestir_kimlik_kabul():
    """'stil' geçerli hedef; olmayan dosyada Türkçe 'bulunamadı' hatası."""
    sonuc = subprocess.run(
        [sys.executable, str(KOD / "gorsel.py"), str(KOK / "bolumler" / "bolum_01" / "senaryo.json"),
         "--yerlestir", "stil", "olmayan_dosya.png", "--yeniden"],
        capture_output=True, encoding="utf-8", errors="replace")
    assert sonuc.returncode == 1
    assert "Bilinmeyen hedef" not in sonuc.stdout, sonuc.stdout
    assert "bulunamadı" in sonuc.stdout, sonuc.stdout


def test_promptlar_uc_farkli_gorsel_ister():
    t = karakter_tarifleri(HIKAYE)
    for p in (sahne_promptu(ornek_sahne(1, ["sen"]), t), sahne_promptu(ornek_sahne(1, []), t),
              karakter_promptu(t["sen"]), karakter_promptu(t["sen"], stil_var=True)):
        son = p.strip().splitlines()[-1]
        assert "3 farklı görsel" in son, son
    assert "kamera açısı" in sahne_promptu(ornek_sahne(1, ["sen"]), t)


# --- Mekân tarifi (hikaye.md: Mekânlar + Renk paleti) ---

def test_mekan_tarifleri_hikaye_mdden():
    m = mekan_tarifleri(HIKAYE)
    assert set(m) == {"otobus", "tesis", "istasyon", "dis"}, set(m)
    assert "lacivert kumaş koltuklar" in m["otobus"] and "mor" in m["otobus"]
    assert "floresan" in m["tesis"].lower() and "yeşilimsi" in m["tesis"]
    assert "tek pompalı" in m["istasyon"] and "sodyum" in m["istasyon"]
    assert "dağ silüetleri" in m["dis"]
    assert "**" not in "".join(m.values())
    assert "kurgusal" not in m["tesis"] and "ipucu" not in m["otobus"]  # yazar notları prompta girmez


def test_sahne_promptu_mekan_ekler():
    t = karakter_tarifleri(HIKAYE)
    sahne = dict(ornek_sahne(1, ["sen"]), mekan="otobus")
    p = sahne_promptu(sahne, t, mekanlar=mekan_tarifleri(HIKAYE))
    assert "Mekân:" in p and "lacivert kumaş koltuklar" in p, p
    assert p.index("Mekân:") < p.index("Sahne:")


def test_sahne_promptu_mekansiz():
    t = karakter_tarifleri(HIKAYE)
    p = sahne_promptu(ornek_sahne(1, ["sen"]), t, mekanlar=mekan_tarifleri(HIKAYE))
    assert "Mekân:" not in p


def test_sahne_promptu_poz_vurgusu():
    p = sahne_promptu(ornek_sahne(1, ["sen"]), karakter_tarifleri(HIKAYE))
    assert "bakış yönü" in p


def test_istekler_mekan_ekler():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        bos_dosya(kok / "karakterler" / "sen.png")
        veri = ornek_veri()
        veri["sahneler"][0]["mekan"] = "tesis"
        metin = istekler_metni(veri, karakter_tarifleri(HIKAYE), kok, mekan_tarifleri(HIKAYE))
        s1 = metin[metin.index("## Sahne 1"):metin.index("## Sahne 2")]
        assert "Kuşkonmaz" in s1, s1


# --- Seçim kartı görselleri ---

def gorselli_veri():
    veri = ornek_veri()
    veri["ikilem"]["secenekler"] = {"A": {"metin": "Zarfı aç", "gorsel": "Açılmış zarf, içinde kâğıt."},
                                    "B": "Söz verdin, açma"}
    return veri


def test_secenek_hedefi():
    assert secenek_hedefi("secenekA") == "A"
    assert secenek_hedefi("secenek_b") == "B"
    assert secenek_hedefi("secenekC") is None
    assert secenek_hedefi("riza") is None


def test_secenek_yolu():
    assert secenek_yolu(Path("g"), "A") == Path("g") / "secenek_A.png"


def test_secenek_gorselleri_yalnizca_tarifliler():
    assert secenek_gorselleri(gorselli_veri()) == {"A": ("Zarfı aç", "Açılmış zarf, içinde kâğıt.")}
    assert secenek_gorselleri(ornek_veri()) == {}
    veri = ornek_veri()
    del veri["ikilem"]["secenekler"]
    assert secenek_gorselleri(veri) == {}


def test_secenek_promptu():
    p = secenek_promptu("A", "Zarfı aç", "Açılmış zarf.", stil_var=True)
    assert "Kare 1:1" in p and "Açılmış zarf." in p and "Zarfı aç" in p
    assert "Ekteki 1. görsel yalnızca çizim tarzı" in p
    assert "3 farklı görsel" in p
    assert "Ekteki" not in secenek_promptu("A", "x", "y")


def test_istekler_secim_karti_bolumu():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        bos_dosya(kok / "karakterler" / "stil.png")
        metin = istekler_metni(gorselli_veri(), karakter_tarifleri(HIKAYE), kok)
        assert "## Seçim kartı A" in metin, metin
        assert "## Seçim kartı B" not in metin
        bolum = metin[metin.index("## Seçim kartı A"):]
        assert "karakterler/stil.png" in bolum and "--yerlestir secenekA" in bolum
        assert "Açılmış zarf" in bolum
        assert metin.index("## Sahne 3") < metin.index("## Seçim kartı A")


def test_durum_secim_karti():
    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        g = kok / "gorseller"
        metin = durum_metni(gorselli_veri(), g, kok)
        assert "Seçim kartı A: yok" in metin, metin
        assert "Seçim kartı B" not in metin
        bos_dosya(secenek_yolu(g, "A"))
        bos_dosya(secenek_yolu(g, "B"))
        metin = durum_metni(gorselli_veri(), g, kok)
        assert "Seçim kartı A: hazır" in metin, metin
        assert "Seçim kartı B: hazır (senaryoda tarif yok)" in metin, metin


def test_oran_uyarisi_kare():
    assert oran_uyarisi(1024, 1024, (1080, 1080)) is None
    uyari = oran_uyarisi(1080, 1920, (1080, 1080))
    assert uyari and "kare (1:1)" in uyari


def test_secenege_yerlestir_kare():
    if not FFMPEG:
        print("  (ffmpeg yok, atlandı)")
        return
    with tempfile.TemporaryDirectory() as d:
        kaynak, hedef = Path(d) / "k.png", Path(d) / "g" / "secenek_A.png"
        png_uret(kaynak, 1024, 1024)
        assert secenege_yerlestir(kaynak, hedef) is None
        assert boyut_oku(hedef) == (1080, 1080)
        png_uret(kaynak, 768, 1344)
        assert secenege_yerlestir(kaynak, hedef) is not None
        assert boyut_oku(hedef) == (1080, 1080)


def test_cli_secenek_iki_dosya_hata():
    sonuc = subprocess.run(
        [sys.executable, str(KOD / "gorsel.py"), str(KOK / "bolumler" / "bolum_01" / "senaryo.json"),
         "--yerlestir", "secenekA", "x.png", "y.png"],
        capture_output=True, encoding="utf-8", errors="replace")
    assert sonuc.returncode == 1
    assert "tek dosya" in sonuc.stdout, sonuc.stdout


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    testler = [(ad, f) for ad, f in sorted(globals().items())
               if ad.startswith("test_")]
    basarisiz = 0
    for ad, f in testler:
        try:
            f()
        except AssertionError as e:
            basarisiz += 1
            print(f"BAŞARISIZ  {ad}: {e}")
    if basarisiz:
        print(f"\n{basarisiz}/{len(testler)} test başarısız.")
        sys.exit(1)
    print(f"Tüm testler geçti ({len(testler)}).")
