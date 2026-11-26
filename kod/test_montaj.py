"""montaj.py için testler.

Çalıştırma:  python kod/test_montaj.py
Ek kütüphane gerekmez. ffmpeg'siz kısımlar her zaman denenir; ffmpeg kuruluysa
küçük üretilmiş görsel ve seslerle uçtan uca bir video da üretilir.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOD = Path(__file__).resolve().parent
KOK = KOD.parent
sys.path.insert(0, str(KOD))

from montaj import (  # noqa: E402
    FONT_ADI,
    CumleGirdisi,
    MontajHatasi,
    SahneGirdisi,
    altyazi_olaylari,
    ass_kacir,
    ass_metni,
    ass_zaman,
    birlestirme_komutu,
    girdileri_topla,
    gruplara_bol,
    kart_olaylari,
    klip_komutu,
    montajla,
    sahne_secimi,
    ses_filtresi,
    varyant_secimi,
    zaman_cizelgesi,
)

GERCEK_ZAMANLAMA = KOK / "bolumler" / "bolum_01" / "sesler" / "zamanlama.json"
IKILEM = {"soru": "Teyze kayıp. Zarfı şimdi açacak mısın?",
          "secenekler": {"A": "Zarfı aç", "B": "Söz verdin, açma"}}

basarili = basarisiz = 0


def kontrol(ad, kosul, ayrinti=""):
    global basarili, basarisiz
    if kosul:
        basarili += 1
    else:
        basarisiz += 1
        print(f"✗ {ad} {ayrinti}")


def hata_bekle(ad, fonk, icerik=None):
    try:
        fonk()
    except MontajHatasi as e:
        metin = "\n".join(e.hatalar)
        if icerik is None or all(p in metin for p in ([icerik] if isinstance(icerik, str) else icerik)):
            kontrol(ad, True)
        else:
            kontrol(ad, False, f"mesaj beklenen parçayı içermiyor: {metin!r}")
        return
    kontrol(ad, False, "MontajHatasi bekleniyordu")


def kelime(k, b, s):
    return {"kelime": k, "baslangic": b, "bitis": s}


def ornek_veri(bolum=1, sahne_sayisi=2):
    sahneler = []
    for no in range(1, sahne_sayisi + 1):
        sahneler.append({"no": no, "gorsel": "x", "karakterler": [],
                         "cumleler": [{"konusan": "anlatici", "metin": f"Sahne {no} bir."},
                                      {"konusan": "anlatici", "metin": f"Sahne {no} iki."}]})
    return {"bolum": bolum, "baslik": "Deneme", "sahneler": sahneler, "ikilem": IKILEM}


def sahte_bolum(kok, veri, gorseller=("a",), eksik_mp3=(), eksik_kayit=(), eski=()):
    """Geçici klasörde bölüm kurar: boş png'ler, sahte mp3'ler, zamanlama.json."""
    klasor = Path(kok) / f"bolum_{veri['bolum']:02d}"
    (klasor / "gorseller").mkdir(parents=True)
    (klasor / "sesler").mkdir()
    kayitlar = {}
    for sahne in veri["sahneler"]:
        for harf in gorseller:
            (klasor / "gorseller" / f"sahne{sahne['no']}_{harf}.png").write_bytes(b"png")
        for i, c in enumerate(sahne["cumleler"], 1):
            anahtar = f"s{sahne['no']:02d}_c{i}"
            if anahtar not in eksik_mp3:
                (klasor / "sesler" / f"{anahtar}.mp3").write_bytes(b"mp3")
            if anahtar not in eksik_kayit:
                metin = "ESKİ METİN" if anahtar in eski else c["metin"]
                kayitlar[anahtar] = {"metin": metin, "dosya": f"{anahtar}.mp3",
                                     "kelimeler": [kelime("Sahne", 0.0, 0.3)]}
    # senaryoda olmayan eski kayıt (cümle silinmiş): yok sayılmalı
    kayitlar["s01_c9"] = {"metin": "silinmiş", "dosya": "s01_c9.mp3", "kelimeler": []}
    (klasor / "sesler" / "s01_c9.mp3").write_bytes(b"mp3")
    (klasor / "sesler" / "zamanlama.json").write_text(
        json.dumps({"bolum": veri["bolum"], "cumleler": kayitlar}, ensure_ascii=False),
        encoding="utf-8")
    return klasor


# --- Task 1: bayraklar ---

def test_sahne_secimi():
    veri = ornek_veri(sahne_sayisi=4)
    kontrol("sahne None → hepsi", sahne_secimi(None, veri) == [1, 2, 3, 4])
    kontrol("sahne '3'", sahne_secimi("3", veri) == [3])
    kontrol("sahne '1-3'", sahne_secimi("1-3", veri) == [1, 2, 3])
    kontrol("sahne ' 2 - 4 '", sahne_secimi(" 2 - 4 ", veri) == [2, 3, 4])
    hata_bekle("sahne 0", lambda: sahne_secimi("0", veri), "0")
    hata_bekle("sahne 9", lambda: sahne_secimi("9", veri), "9")
    hata_bekle("sahne ters aralık", lambda: sahne_secimi("3-1", veri))
    hata_bekle("sahne yazı", lambda: sahne_secimi("x", veri))


def test_varyant_secimi():
    veri = ornek_veri(sahne_sayisi=5)
    kontrol("varyant None", varyant_secimi(None, veri) == {})
    kontrol("varyant '3=b,5=c'", varyant_secimi("3=b,5=c", veri) == {3: "b", 5: "c"})
    kontrol("varyant büyük harf", varyant_secimi("3=B", veri) == {3: "b"})
    hata_bekle("varyant harf d", lambda: varyant_secimi("3=d", veri), "3=d")
    hata_bekle("varyant olmayan sahne", lambda: varyant_secimi("99=a", veri), "99")
    hata_bekle("varyant bozuk", lambda: varyant_secimi("3b", veri))


# --- Task 1: girdiler ---

def test_girdileri_topla():
    veri = ornek_veri()
    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri, gorseller=("a", "b"))
        girdiler = girdileri_topla(veri, klasor, [1, 2], {2: "b"})
        kontrol("girdi sahne sayısı", [g.no for g in girdiler] == [1, 2])
        kontrol("varsayılan varyant a", girdiler[0].gorsel.name == "sahne1_a.png")
        kontrol("varyant b", girdiler[1].gorsel.name == "sahne2_b.png")
        anahtarlar = [c.anahtar for g in girdiler for c in g.cumleler]
        kontrol("senaryo sırası, eski kayıt yok sayılır",
                anahtarlar == ["s01_c1", "s01_c2", "s02_c1", "s02_c2"], anahtarlar)
        kontrol("mp3 yolu", girdiler[0].cumleler[1].mp3 == klasor / "sesler" / "s01_c2.mp3")
        kontrol("kelimeler", girdiler[0].cumleler[0].kelimeler[0]["kelime"] == "Sahne")
        kontrol("yalnızca istenen sahne", [g.no for g in girdileri_topla(veri, klasor, [2], {})] == [2])

    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri, gorseller=("a",), eksik_mp3=("s01_c2",),
                             eksik_kayit=("s02_c1",), eski=("s02_c2",))
        (klasor / "gorseller" / "sahne1_a.png").unlink()
        try:
            girdileri_topla(veri, klasor, [1, 2], {2: "c"})
            kontrol("eksikler hata verir", False)
        except MontajHatasi as e:
            metin = "\n".join(e.hatalar)
            kontrol("eksik görsel sahne1_a", "sahne1_a.png" in metin, metin)
            kontrol("eksik varyant sahne2_c", "sahne2_c.png" in metin, metin)
            kontrol("görsel komutu", "--yerlestir 1" in metin, metin)
            kontrol("eksik mp3", "s01_c2.mp3" in metin, metin)
            kontrol("eksik kayıt", "s02_c1" in metin, metin)
            kontrol("eski metin", "s02_c2" in metin and "eski" in metin, metin)
            kontrol("ses komutu", "--sahne 2" in metin, metin)
            kontrol("hepsi birden", len(e.hatalar) >= 5, e.hatalar)

    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri)
        (klasor / "sesler" / "zamanlama.json").unlink()
        hata_bekle("zamanlama.json yok", lambda: girdileri_topla(veri, klasor, [1], {}), "s01_c1")


# --- Task 1: zaman çizelgesi ---

def _girdiler():
    return [
        SahneGirdisi(1, Path("g1.png"), [CumleGirdisi("s01_c1", Path("s01_c1.mp3"), []),
                                         CumleGirdisi("s01_c2", Path("s01_c2.mp3"), [])]),
        SahneGirdisi(2, Path("g2.png"), [CumleGirdisi("s02_c1", Path("s02_c1.mp3"), [])]),
    ]


def test_zaman_cizelgesi():
    c = zaman_cizelgesi(_girdiler(), {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.234})
    kontrol("sahne1 başlangıç", c.sahneler[0][2] == 0.0)
    kontrol("sahne1 kare (3.5 sn)", c.sahneler[0][3] == 105, c.sahneler[0])
    kontrol("sahne2 başlangıç", abs(c.sahneler[1][2] - 3.5) < 1e-9, c.sahneler[1])
    kontrol("sahne2 kare", c.sahneler[1][3] == round((1.234 + 0.35) * 30), c.sahneler[1])
    bas = {k[0]: k[2] for k in c.cumleler}
    kontrol("s01_c2 başlangıç", abs(bas["s01_c2"] - 1.15) < 1e-9, bas)
    kontrol("s02_c1 başlangıç", abs(bas["s02_c1"] - 3.5) < 1e-9, bas)
    slot = {k[0]: k[3] for k in c.cumleler}
    kontrol("slot sonraki cümleye kadar", abs(slot["s01_c1"] - 1.15) < 1e-9, slot)
    kontrol("sahne son slot sahne bitişi", abs(slot["s01_c2"] - 3.5) < 1e-9, slot)
    kart = (105 + round(1.584 * 30)) / 30
    kontrol("kart başlangıç", abs(c.kart_baslangic - kart) < 1e-9, c.kart_baslangic)
    kontrol("kart kare 120", c.kart_kare == 120)
    kontrol("toplam", abs(c.toplam - (kart + 4)) < 1e-9, c.toplam)


def test_yuvarlama_birikmez():
    girdiler = [SahneGirdisi(n, Path(f"g{n}.png"), [CumleGirdisi(f"s{n:02d}_c1", Path("x"), [])])
                for n in range(1, 13)]
    c = zaman_cizelgesi(girdiler, {f"s{n:02d}_c1": 2.0173 for n in range(1, 13)})
    toplam_kare = 0
    for sahne, cumle in zip(c.sahneler, c.cumleler):
        kontrol("sahne başı = önceki kareler/30", abs(sahne[2] - toplam_kare / 30) < 1e-9)
        kontrol("cümle sahne başında", abs(cumle[2] - sahne[2]) < 1e-9)
        kontrol("slot = sahne sonu", abs(cumle[3] - (toplam_kare + sahne[3]) / 30) < 1e-9)
        toplam_kare += sahne[3]
    kontrol("kart klip sınırında", abs(c.kart_baslangic - toplam_kare / 30) < 1e-9)


# --- Task 2: altyazı ---

def _metinler(gruplar):
    return [" ".join(k["kelime"] for k in g) for g in gruplar]


def test_gruplara_bol():
    kayit = json.loads(GERCEK_ZAMANLAMA.read_text(encoding="utf-8"))["cumleler"]["s03_c1"]
    gruplar = _metinler(gruplara_bol(kayit["kelimeler"]))
    kontrol("gerçek s03_c1 grupları", gruplar == [
        "Ben Nadide.", "Gece yolculuğu uzun", "olur evladım,", "biraz laflarız."], gruplar)
    kontrol("tek kelime", _metinler(gruplara_bol([kelime("Teyze?", 0, 0.5)])) == ["Teyze?"])
    uzun = [kelime(k, i, i + 0.5) for i, k in enumerate("bir iki üç dört beş altı yedi".split())]
    kontrol("en çok 4 kelime", _metinler(gruplara_bol(uzun)) ==
            ["bir iki üç dört", "beş altı yedi"], _metinler(gruplara_bol(uzun)))
    virgul = [kelime("Evet,", 0, 1), kelime("tamam", 1, 2), kelime("dedi.", 2, 3)]
    kontrol("tek kelimede virgül grubu kapatmaz",
            _metinler(gruplara_bol(virgul)) == ["Evet, tamam dedi."], _metinler(gruplara_bol(virgul)))
    cok_uzun = [kelime("Pencereden", 0, 1), kelime("dışarıdakilere", 1, 2)]
    kontrol("22 karakteri aşan tek kelime kendi grubunda",
            _metinler(gruplara_bol([kelime("a" * 30, 0, 1), kelime("b", 1, 2)])) == ["a" * 30, "b"])
    kontrol("tam 22 karakter sığar (10+1+11)",
            _metinler(gruplara_bol([kelime("a" * 10, 0, 1), kelime("b" * 11, 1, 2)])) ==
            ["a" * 10 + " " + "b" * 11])
    kontrol("boş liste", gruplara_bol([]) == [])
    _ = cok_uzun


def test_ass_yardimcilari():
    kontrol("ass_zaman 0", ass_zaman(0) == "0:00:00.00")
    kontrol("ass_zaman 61.237", ass_zaman(61.237) == "0:01:01.24", ass_zaman(61.237))
    kontrol("ass_zaman 3599.999", ass_zaman(3599.999) == "1:00:00.00", ass_zaman(3599.999))
    kontrol("ass_kacir", ass_kacir("a{b}\\c") == "a(b)/c", ass_kacir("a{b}\\c"))
    kontrol("ass_kacir satır sonu", "\n" not in ass_kacir("a\nb"))


def test_altyazi_olaylari():
    girdiler = [SahneGirdisi(1, Path("g.png"), [
        CumleGirdisi("s01_c1", Path("x"), [kelime("Ben", 0.0, 0.3), kelime("Nadide.", 0.36, 1.16),
                                            kelime("Gece", 1.44, 1.68), kelime("uzun.", 1.76, 2.3)]),
        CumleGirdisi("s01_c2", Path("y"), [kelime("Teyze?", 0.1, 0.6)]),
    ])]
    c = zaman_cizelgesi(girdiler, {"s01_c1": 2.4, "s01_c2": 0.7})
    olaylar = altyazi_olaylari(c)
    kontrol("olay sayısı = kelime sayısı", len(olaylar) == 5, len(olaylar))
    kontrol("Dialogue satırı", all(o.startswith("Dialogue: ") for o in olaylar))
    kontrol("ilk olay: Ben sarı", "{\\c&H002DB8E8&}Ben{\\c&H00FFFFFF&} Nadide." in olaylar[0], olaylar[0])
    kontrol("ilk olay 0'da başlar, Nadide'ye kadar", ",0:00:00.00,0:00:00.36," in olaylar[0], olaylar[0])
    kontrol("grup sonu → sonraki grup başı", ",0:00:00.36,0:00:01.44," in olaylar[1], olaylar[1])
    kontrol("ikinci grup metni", "Gece" in olaylar[2] and "Nadide" not in olaylar[2], olaylar[2])
    # cümle sonu: bitis 2.3 + 0.3 = 2.6 ama slot 2.55'te bitiyor (2.4 + 0.15)
    kontrol("cümle sonu slotu aşmaz", ",0:00:01.76,0:00:02.55," in olaylar[3], olaylar[3])
    # ikinci cümle 2.55'te başlar: 2.55+0.1 → 2.55+0.6+0.3 (sahne sonu 3.6'dan önce)
    kontrol("ikinci cümle mutlak zaman", ",0:00:02.65,0:00:03.45," in olaylar[4], olaylar[4])


def test_kart_olaylari():
    olaylar = "\n".join(kart_olaylari(IKILEM, 10.0, 4.0))
    kontrol("kart soru", "Zarfı şimdi açacak mısın?" in olaylar)
    kontrol("kart A", "Zarfı aç" in olaylar and "Söz verdin, açma" in olaylar)
    kontrol("kart not", "Yorumlara A ya da B yaz" in olaylar)
    kontrol("kart zamanı", "0:00:10.00,0:00:14.00" in olaylar, olaylar)
    kontrol("kart fade", "\\fad(" in olaylar)
    son = "\n".join(kart_olaylari({"soru": "Sence bu gece gerçekten ne oldu?"}, 0, 4))
    kontrol("bölüm 8: soru", "ne oldu?" in son)
    kontrol("bölüm 8: Yorumlara yaz", "Yorumlara yaz" in son and "A ya da B" not in son, son)
    kontrol("bölüm 8: kutu yok", "Secenek" not in son, son)


def test_ass_metni():
    c = zaman_cizelgesi(_girdiler(), {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0})
    metin = ass_metni(c, IKILEM)
    kontrol("ass PlayResY", "PlayResY: 1920" in metin and "PlayResX: 1080" in metin)
    kontrol("ass font", f",{FONT_ADI}," in metin)
    kontrol("ass stiller", all(f"Style: {s}," in metin for s in ("Alt", "Soru", "Secenek", "Not")))
    kontrol("ass kart", "Zarfı aç" in metin)


# --- Task 3: komutlar ---

def test_komutlar():
    k = klip_komutu("g/sahne1_a.png", 90, 1.0, 1.08, "klip1.mp4")
    kontrol("klip liste", isinstance(k, list) and all(isinstance(p, str) for p in k))
    metin = " ".join(k)
    kontrol("klip zoompan", "zoompan" in metin and "1080x1920" in metin, metin)
    kontrol("klip kare", "-frames:v" in k and k[k.index("-frames:v") + 1] == "90")
    kontrol("klip girdi", "g/sahne1_a.png" in k)
    kontrol("klip karartma yok", "colorchannelmixer" not in metin)
    kontrol("kart karartma", "colorchannelmixer" in " ".join(
        klip_komutu("g.png", 120, 1.04, 1.04, "kart.mp4", karart=True)))

    c = zaman_cizelgesi(_girdiler(), {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0})
    f = ses_filtresi(c, 1)
    kontrol("ses concat", "concat=n=4:v=0:a=1" in f, f)
    kontrol("ses girdi 1..3", "[1:a]" in f and "[3:a]" in f and "[4:a]" not in f, f)
    kontrol("ses kart sessizlik", "anullsrc" in f and "duration=4" in f, f)
    kontrol("ses çıkış", f.endswith("[ses]"), f)

    b = birlestirme_komutu("klipler.txt", ["../sesler/s01_c1.mp3"], "altyazi.ass",
                           "../../varliklar/fontlar", f, "cikti.mp4")
    bm = " ".join(b)
    kontrol("birleştirme concat", "-f concat" in bm and "klipler.txt" in b)
    kontrol("birleştirme ass", "ass=altyazi.ass:fontsdir=../../varliklar/fontlar" in bm, bm)
    kontrol("birleştirme mutlak yol yok", ":\\" not in bm and "C:" not in bm, bm)
    kontrol("birleştirme kodlama", "libx264" in b and "aac" in b and "+faststart" in b)


# --- Task 3: uçtan uca (ffmpeg varsa) ---

def _uret(komut):
    subprocess.run(komut, check=True, capture_output=True)


def test_uctan_uca():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        print("- uçtan uca test atlandı (ffmpeg yok)")
        return
    veri = ornek_veri(sahne_sayisi=2)
    veri["sahneler"] = veri["sahneler"][:2]
    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri)
        for n, renk in ((1, "navy"), (2, "purple")):
            _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={renk}:s=1080x1920",
                   "-frames:v", "1", str(klasor / "gorseller" / f"sahne{n}_a.png")])
        for mp3 in (klasor / "sesler").glob("s0*_c*.mp3"):
            _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                   "-t", "0.5", "-c:a", "libmp3lame", str(mp3)])
        cikti = montajla(veri, klasor, [2], {})
        kontrol("önizleme adı", cikti == klasor / "onizleme.mp4", cikti)
        sure = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(cikti)], capture_output=True, encoding="utf-8").stdout.strip())
        beklenen = round((0.5 * 2 + 0.15 + 0.35) * 30) / 30 + 4
        kontrol("video süresi", abs(sure - beklenen) < 0.15, f"{sure} != {beklenen}")
        boyut = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "csv=p=0:s=x", str(cikti)],
            capture_output=True, encoding="utf-8").stdout.strip()
        kontrol("video 1080x1920", boyut == "1080x1920", boyut)
        kontrol("geçici klasör silindi",
                [p.name for p in klasor.iterdir() if p.is_dir()] == ["gorseller", "sesler"],
                list(klasor.iterdir()))
        # hedef değiştirilemiyorsa (Windows'ta video oynatıcıda açık) anlaşılır hata
        cikti.unlink()
        cikti.mkdir()
        (cikti / "kilit").write_bytes(b"")
        hata_bekle("hedef yazılamıyor", lambda: montajla(veri, klasor, [2], {}), "onizleme.mp4")
        kontrol("hata sonrası geçici klasör silindi",
                not any(p.name.startswith(".montaj_") for p in klasor.iterdir()))
        shutil.rmtree(cikti)
        kontrol("kuru çalışma video üretmez", montajla(veri, klasor, [1, 2], {}, kuru=True) is None
                and not (klasor / "video.mp4").exists())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for ad, fonk in list(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            fonk()
    print(f"{basarili} başarılı, {basarisiz} başarısız")
    sys.exit(1 if basarisiz else 0)
