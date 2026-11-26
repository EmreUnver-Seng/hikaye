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
    CUMLE_ARASI,
    CUMLE_SONU_PAYI,
    FONT_ADI,
    KANCA_BIT,
    KART_SES_BAS,
    KART_SES_SONU,
    SAHNE_SONU,
    KART_XLER,
    KART_Y,
    SAAT_BOYUT,
    SAAT_X,
    SAAT_Y,
    CumleGirdisi,
    KartSecenegi,
    MontajHatasi,
    SaatGirdisi,
    SaatPlani,
    SahneGirdisi,
    Ambiyans,
    altyazi_olaylari,
    ambiyans_filtresi,
    ambiyans_plani,
    ass_kacir,
    ass_metni,
    ass_zaman,
    birlestirme_komutu,
    girdileri_topla,
    kanca_olaylari,
    kart_sesi,
    normallestirme_komutu,
    olcumu_oku,
    gruplara_bol,
    kart_komutu,
    kart_olaylari,
    kart_plani,
    klip_komutu,
    montajla,
    sahne_secimi,
    saat_filtresi,
    saat_girdisi,
    satirlara_bol,
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
    kare1 = round((1.0 + CUMLE_ARASI + 2.0 + SAHNE_SONU) * 30)
    bas2 = kare1 / 30
    kontrol("sahne1 kare", c.sahneler[0][3] == kare1, c.sahneler[0])
    kontrol("sahne2 başlangıç", abs(c.sahneler[1][2] - bas2) < 1e-9, c.sahneler[1])
    kontrol("sahne2 kare", c.sahneler[1][3] == round((1.234 + SAHNE_SONU) * 30), c.sahneler[1])
    bas = {k[0]: k[2] for k in c.cumleler}
    kontrol("s01_c2 başlangıç", abs(bas["s01_c2"] - (1.0 + CUMLE_ARASI)) < 1e-9, bas)
    kontrol("s02_c1 başlangıç", abs(bas["s02_c1"] - bas2) < 1e-9, bas)
    slot = {k[0]: k[3] for k in c.cumleler}
    kontrol("slot sonraki cümleye kadar", abs(slot["s01_c1"] - (1.0 + CUMLE_ARASI)) < 1e-9, slot)
    kontrol("sahne son slot sahne bitişi", abs(slot["s01_c2"] - bas2) < 1e-9, slot)
    kart = (kare1 + round((1.234 + SAHNE_SONU) * 30)) / 30
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
        "Ben Fatma.", "Gece yolculuğu uzun", "olur evladım,", "biraz laflarız."], gruplar)
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
        CumleGirdisi("s01_c1", Path("x"), [kelime("Ben", 0.0, 0.3), kelime("Fatma.", 0.36, 1.16),
                                            kelime("Gece", 1.44, 1.68), kelime("uzun.", 1.76, 2.3)]),
        CumleGirdisi("s01_c2", Path("y"), [kelime("Teyze?", 0.1, 0.6)]),
    ])]
    # s01_c1'in sesi 2.0 sn ama son kelime 2.3'te bitiyor (zamanlama tahmini sesi aşabilir):
    # altyazı yine de cümlenin slotunda (2.0 + CUMLE_ARASI) kesilmeli.
    c = zaman_cizelgesi(girdiler, {"s01_c1": 2.0, "s01_c2": 0.7})
    slot1 = 2.0 + CUMLE_ARASI
    olaylar = altyazi_olaylari(c)
    kontrol("olay sayısı = kelime sayısı", len(olaylar) == 5, len(olaylar))
    kontrol("Dialogue satırı", all(o.startswith("Dialogue: ") for o in olaylar))
    kontrol("ilk olay: Ben sarı", "{\\c&H002DB8E8&}Ben{\\c&H00FFFFFF&} Fatma." in olaylar[0], olaylar[0])
    kontrol("ilk olay 0'da başlar, Fatma'ya kadar", ",0:00:00.00,0:00:00.36," in olaylar[0], olaylar[0])
    kontrol("grup sonu → sonraki grup başı", ",0:00:00.36,0:00:01.44," in olaylar[1], olaylar[1])
    kontrol("ikinci grup metni", "Gece" in olaylar[2] and "Fatma" not in olaylar[2], olaylar[2])
    son1 = min(2.3 + CUMLE_SONU_PAYI, slot1)
    kontrol("cümle sonu slotu aşmaz", son1 <= slot1 and
            f",0:00:01.76,{ass_zaman(son1)}," in olaylar[3], olaylar[3])
    # ikinci cümle slot1'de başlar: slot1+0.1 → slot1+0.6+0.3
    kontrol("ikinci cümle mutlak zaman",
            f",{ass_zaman(slot1 + 0.1)},{ass_zaman(slot1 + 0.6 + CUMLE_SONU_PAYI)}," in olaylar[4],
            olaylar[4])


def test_kart_olaylari():
    olaylar = "\n".join(kart_olaylari(IKILEM, 10.0, 4.0))
    kontrol("kart soru", "Zarfı şimdi açacak mısın?" in olaylar)
    kontrol("kart A, B", "Zarfı aç" in olaylar and "Söz verdin," in olaylar and "açma" in olaylar)
    kontrol("kart not", "Yorumlara A ya da B yaz" in olaylar)
    kontrol("kart zamanı", "0:00:10.25,0:00:14.00" in olaylar, olaylar)
    kontrol("soru da belirir", all("fad(" in o for o in kart_olaylari(IKILEM, 10.0, 4.0)))
    kontrol("kart fade", "\\fad(" in olaylar)
    son = "\n".join(kart_olaylari({"soru": "Sence bu gece gerçekten ne oldu?"}, 0, 4))
    kontrol("bölüm 8: soru", "ne oldu?" in son)
    kontrol("bölüm 8: Yorumlara yaz", "Yorumlara yaz" in son and "A ya da B" not in son, son)
    kontrol("bölüm 8: kart yok", ",Kart," not in son and ",Harf," not in son, son)
    kontrol("yedek düzen: büyük harf", olaylar.count(",Harf,") == 2, olaylar)


def test_kart_olaylari_gorselli():
    plan = [KartSecenegi("A", "Zarfı aç", Path("g/secenek_A.png"), True),
            KartSecenegi("B", "Söz verdin, açma", None, True)]
    olaylar = kart_olaylari(IKILEM, 10.0, 4.0, plan)
    metin = "\n".join(olaylar)
    a = next(o for o in olaylar if "Zarfı aç" in o)
    b = next(o for o in olaylar if "açma" in o)
    kontrol("görselli kartta harf + metin", ",Kart," in a and "}A{" in a and "\\N" in a, a)
    kontrol("A solda", f"\\pos({KART_XLER[0] + 225}," in a, a)
    kontrol("B sağda", f"\\pos({KART_XLER[1] + 225}," in b, b)
    kontrol("görselsiz B büyük harfli", metin.count(",Harf,") == 1, metin)
    kontrol("B metni iki satır", "Söz verdin,\\Naçma" in b, b)
    kontrol("çağrı kartların altında", f"\\pos(540,{KART_Y + 640 + 90})" in metin, metin)


def test_satirlara_bol():
    kontrol("kısa tek satır", satirlara_bol("Zarfı aç") == ["Zarfı aç"])
    kontrol("uzun bölünür", satirlara_bol("Söz verdin, açma") == ["Söz verdin,", "açma"])
    kontrol("tek uzun kelime", satirlara_bol("Kuşkonmazlılaştıramadıklarımız") ==
            ["Kuşkonmazlılaştıramadıklarımız"])


def test_kart_plani():
    with tempfile.TemporaryDirectory() as tmp:
        g = Path(tmp)
        (g / "secenek_A.png").write_bytes(b"png")
        ikilem = {"soru": "?", "secenekler": {"A": {"metin": "Aç", "gorsel": "zarf"}, "B": "Açma"}}
        plan = kart_plani(ikilem, g)
        kontrol("plan sırası", [k.harf for k in plan] == ["A", "B"], plan)
        kontrol("A görselli", plan[0].gorsel == g / "secenek_A.png" and plan[0].tarif, plan)
        kontrol("B görselsiz", plan[1].gorsel is None and not plan[1].tarif, plan)
        kontrol("metin okunur", plan[0].metin == "Aç" and plan[1].metin == "Açma", plan)
        kontrol("bölüm 8 boş plan", kart_plani({"soru": "?"}, g) == [])


def test_kart_sesli_cizelge():
    sureler = {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0}
    c = zaman_cizelgesi(_girdiler(), sureler, kart_sure=5.0)
    beklenen = round((KART_SES_BAS + 5.0 + KART_SES_SONU) * 30)
    kontrol("kart okuma kadar uzar", c.kart_sesli and c.kart_kare == beklenen, c.kart_kare)
    kisa = zaman_cizelgesi(_girdiler(), sureler, kart_sure=0.5)
    kontrol("kart en az 4 sn", kisa.kart_kare == 120, kisa.kart_kare)
    f = ses_filtresi(c, 1)
    kontrol("kart sesi 4. girdi", "[4:a]" in f and "[5:a]" not in f, f)
    kontrol("kart sesi gecikmeli", f"atrim=duration={KART_SES_BAS:.6f}" in f, f)
    kontrol("kart ses concat", "concat=n=5:v=0:a=1" in f, f)
    kontrol("sessiz kartta girdi yok", "[4:a]" not in ses_filtresi(
        zaman_cizelgesi(_girdiler(), sureler), 1))


def test_kart_sesi():
    veri = ornek_veri()
    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri)
        mp3, uyari = kart_sesi(veri, klasor)
        kontrol("kart okuması yok uyarısı", mp3 is None and "--kart" in uyari, uyari)
        zamanlama = klasor / "sesler" / "zamanlama.json"
        kayitlar = json.loads(zamanlama.read_text(encoding="utf-8"))
        kayitlar["cumleler"]["kart"] = {"metin": "eski soru"}
        zamanlama.write_text(json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
        (klasor / "sesler" / "kart.mp3").write_bytes(b"mp3")
        mp3, uyari = kart_sesi(veri, klasor)
        kontrol("kart okuması eski", mp3 is None and "eski" in uyari, uyari)
        kayitlar["cumleler"]["kart"] = {
            "metin": "Teyze kayıp. Zarfı şimdi açacak mısın? A: Zarfı aç. B: Söz verdin, açma."}
        zamanlama.write_text(json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
        mp3, uyari = kart_sesi(veri, klasor)
        kontrol("kart okuması hazır", mp3 == klasor / "sesler" / "kart.mp3" and uyari is None, uyari)


def test_kanca():
    c = zaman_cizelgesi(_girdiler(), {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0})
    olay = kanca_olaylari("Yanındaki koltuk neden boş?", c)
    kontrol("kanca tek olay", len(olay) == 1, olay)
    kontrol("kanca üstte, 2 sn", "\\an8" in olay[0] and ass_zaman(KANCA_BIT) in olay[0], olay)
    kontrol("kanca iki satır", "\\N" in olay[0], olay)
    kontrol("kanca yoksa olay yok", kanca_olaylari(None, c) == [])
    sadece2 = zaman_cizelgesi(_girdiler()[1:], {"s02_c1": 1.0})
    kontrol("1. sahne yoksa kanca yok", kanca_olaylari("Soru?", sadece2) == [])
    metin = ass_metni(c, IKILEM, kanca="Soru?")
    kontrol("ass kanca stili ve olayı", "Style: Kanca," in metin and ",Kanca,," in metin)


def test_ses_yuksekligi():
    stderr = """[Parsed_loudnorm_0 @ 0x1]
{
	"input_i" : "-23.10",
	"input_tp" : "-4.20",
	"input_lra" : "3.10",
	"input_thresh" : "-33.50",
	"output_i" : "-14.00",
	"target_offset" : "0.30"
}"""
    olcum = olcumu_oku(stderr)
    kontrol("ölçüm okunur", olcum and olcum["input_i"] == "-23.10", olcum)
    kontrol("sessiz ölçüm None", olcumu_oku(stderr.replace('"-23.10"', '"-inf"')) is None)
    kontrol("JSON yoksa None", olcumu_oku("hata") is None)
    k = normallestirme_komutu("cikti.mp4", olcum, "son.mp4")
    km = " ".join(k)
    kontrol("normalizasyon doğrusal", "linear=true" in km and "measured_I=-23.10" in km, km)
    kontrol("normalizasyon video kopyalar", k[k.index("-c:v") + 1] == "copy", k)


def test_ass_metni():
    c = zaman_cizelgesi(_girdiler(), {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0})
    metin = ass_metni(c, IKILEM)
    kontrol("ass PlayResY", "PlayResY: 1920" in metin and "PlayResX: 1080" in metin)
    kontrol("ass font", f",{FONT_ADI}," in metin)
    kontrol("ass stiller", all(f"Style: {s}," in metin for s in ("Alt", "Soru", "Kart", "Harf", "Not")))
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

    plan = [KartSecenegi("A", "Aç", Path("g/secenek_A.png"), True),
            KartSecenegi("B", "Açma", None, False)]
    kk = kart_komutu("g/sahne11_c.png", plan, 120, "kart.mp4")
    km = " ".join(kk)
    kontrol("kart liste", all(isinstance(p, str) for p in kk))
    kontrol("kart karartma", "colorchannelmixer" in km)
    kontrol("kart girdiler", kk.count("-i") == 2 and "g/sahne11_c.png" in kk
            and str(Path("g/secenek_A.png")) in kk, kk)
    kontrol("kartlar yan yana", f"overlay={KART_XLER[0]}:{KART_Y}" in km
            and f"overlay={KART_XLER[1]}:{KART_Y}" in km, km)
    kontrol("yuvarlak köşe", "geq=" in km and "hypot" in km, km)
    kontrol("kart kare sayısı", kk[kk.index("-frames:v") + 1] == "120")
    kontrol("kart tek kareden tekrar", "loop=loop=-1:size=1" in km, km)
    kontrol("kartlar da belirir", "fade=t=in:st=0.25:d=0.4:alpha=1" in km, km)
    kontrol("kart son sahnenin zoom'u", "scale=1166:2074" in " ".join(
        kart_komutu("g.png", plan, 120, "kart.mp4", zoom=1.08)))
    son = kart_komutu("g.png", [], 120, "kart.mp4")
    kontrol("bölüm 8 kartsız", "geq" not in " ".join(son) and son.count("-i") == 1)

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


# --- Saat animasyonu ---

SAAT_GERI = {"bas": "02:45", "bit": "23:30", "yon": "geri", "cumle": 1, "kelime": "23:30"}


def test_saat_girdisi():
    kelimeler = [kelime("saat", 2.96, 3.28), kelime("23:30.", 3.36, 4.48)]
    g = saat_girdisi(SAAT_GERI, kelimeler)
    kontrol("saat başlangıç dakika", g.bas_dk == 165, g)
    kontrol("geri: gece yarısını geçen fark", g.fark_dk == -195, g)
    kontrol("kelime noktalamasız eşleşir", g.kelime_bas == 3.36, g)
    kontrol("cümle sırası 0'dan", g.cumle == 0 and g.es == 0, g)
    ileri = saat_girdisi({"bas": "23:30", "bit": "03:00", "yon": "ileri", "cumle": 1,
                          "kelime": "üç", "es": 1.5}, [kelime("Saat", 0, 0.4), kelime("Üç.", 0.48, 1)])
    kontrol("ileri fark", ileri.fark_dk == 210 and ileri.es == 1.5, ileri)
    kontrol("büyük harf eşleşir", ileri.kelime_bas == 0.48, ileri)
    kontrol("kelime yoksa None", saat_girdisi(SAAT_GERI, [kelime("saat", 0, 1)]) is None)


def test_saat_cizelge():
    saat = SaatGirdisi(165, -195, 1, 0.5, 1.5)
    girdiler = [_girdiler()[0], _girdiler()[1]._replace(saat=saat._replace(cumle=0))]
    c = zaman_cizelgesi(girdiler, {"s01_c1": 1.0, "s01_c2": 2.0, "s02_c1": 1.0})
    bas2 = c.sahneler[1][2]
    kontrol("es cümleyi öteler", abs(c.cumleler[2][2] - (bas2 + 1.5)) < 1e-9, c.cumleler)
    kontrol("es sahneyi uzatır", c.sahneler[1][3] == round((1.5 + 1.0 + SAHNE_SONU) * 30))
    p = c.saatler[2]
    kontrol("duruş = es + kelime", abs(p.durus - 2.0) < 1e-9, p)
    kontrol("katman süresi sahneyi aşmaz", p.sure <= c.sahneler[1][3] / 30 + 1e-9, p)
    kontrol("saatsiz sahne planda yok", 1 not in c.saatler)
    f = ses_filtresi(c, 1)
    kontrol("es: önceki cümle sonraki başlangıca kadar uzar",
            f"whole_dur={c.cumleler[2][2] - c.cumleler[1][2]:.6f}" in f, f)

    ilk = [_girdiler()[0]._replace(saat=SaatGirdisi(0, 60, 0, 0.2, 1.0))]
    c1 = zaman_cizelgesi(ilk, {"s01_c1": 1.0, "s01_c2": 1.0})
    f1 = ses_filtresi(c1, 1)
    kontrol("ilk sahnede es: başta sessizlik", "[bas]" in f1 and "duration=1.000000" in f1
            and "concat=n=4" in f1, f1)


def test_saat_komutu():
    plan = SaatPlani(165, -195, 3.36, 4.66)
    f = saat_filtresi(plan)
    kontrol("saat katmanı boyutu", f"s={SAAT_BOYUT}x{SAAT_BOYUT}" in f, f)
    kontrol("saat süresi", "d=4.6600" in f, f)
    kontrol("ibre zamana bağlı", "T/3.3600" in f and "(165+(-195)*" in f, f)
    kontrol("saydam kenar", "a='" in f, f)
    k = klip_komutu("g.png", 120, 1.0, 1.08, "klip.mp4", saat=plan)
    km = " ".join(k)
    kontrol("saatli klip filter_complex", "-filter_complex" in k and "-vf" not in k, k)
    kontrol("saat üst-ortada", f"overlay={SAAT_X}:{SAAT_Y}:eof_action=pass" in km, km)
    kontrol("saatli klip zoompan", "zoompan" in km and k[k.index("-frames:v") + 1] == "120")

    veri = ornek_veri()
    veri["sahneler"][1]["saat"] = {**SAAT_GERI, "kelime": "yok"}
    with tempfile.TemporaryDirectory() as tmp:
        klasor = sahte_bolum(tmp, veri)
        hata_bekle("saat kelimesi zamanlamada yok",
                   lambda: girdileri_topla(veri, klasor, [1, 2], {}), ["Sahne 2, saat", "'yok'"])
        veri["sahneler"][1]["saat"]["kelime"] = "Sahne"
        g = girdileri_topla(veri, klasor, [1, 2], {})
        kontrol("saat girdisi toplanır", g[1].saat is not None and g[0].saat is None, g)


# --- Task 3: uçtan uca (ffmpeg varsa) ---

def _uret(komut):
    subprocess.run(komut, check=True, capture_output=True)


def _ambiyans_cizelgesi():
    girdiler = [SahneGirdisi(n, Path(f"g{n}.png"), [CumleGirdisi(f"s{n:02d}_c1", Path("x"), [])])
                for n in (1, 2, 3, 4)]
    return zaman_cizelgesi(girdiler, {f"s{n:02d}_c1": 1.0 for n in (1, 2, 3, 4)})


def test_ambiyans_plani():
    c = _ambiyans_cizelgesi()
    veri = ornek_veri(sahne_sayisi=4)
    for s, mekan in zip(veri["sahneler"], ("dis", "otobus", "otobus", "tesis")):
        s["mekan"] = mekan
    with tempfile.TemporaryDirectory() as tmp:
        for m in ("dis", "otobus"):
            (Path(tmp) / f"{m}.mp3").write_bytes(b"mp3")
        parcalar, uyarilar = ambiyans_plani(veri, c, tmp)
        kontrol("ambiyans: ardışık aynı mekân birleşir",
                [p.mekan for p in parcalar] == ["dis", "otobus"], parcalar)
        s = c.sahneler
        kontrol("ambiyans: otobüs 2. sahne başından 3. sahne sonuna",
                abs(parcalar[1].bas - s[1][2]) < 1e-9
                and abs(parcalar[1].bit - (s[2][2] + s[2][3] / 30)) < 1e-9, parcalar)
        kontrol("ambiyans: dosyası olmayan mekân uyarı", len(uyarilar) == 1 and "tesis" in uyarilar[0],
                uyarilar)
        (Path(tmp) / "tesis.mp3").write_bytes(b"mp3")
        parcalar, uyarilar = ambiyans_plani(veri, c, tmp)
        kontrol("ambiyans: son parça kartı kapsar", abs(parcalar[-1].bit - c.toplam) < 1e-9, parcalar)
        kontrol("ambiyans: dosyalar tamsa uyarı yok", uyarilar == [])
        del veri["sahneler"][0]["mekan"]
        parcalar, _ = ambiyans_plani(veri, c, tmp)
        kontrol("ambiyans: mekânsız sahne sessiz", parcalar[0].mekan == "otobus", parcalar)


def test_ambiyans_filtresi():
    kontrol("ambiyans filtresi boş", ambiyans_filtresi([], 5, 10.0) == "")
    parcalar = [Ambiyans("dis", Path("dis.mp3"), 0.0, 4.0), Ambiyans("otobus", Path("o.mp3"), 4.0, 12.0)]
    f = ambiyans_filtresi(parcalar, 5, 12.0)
    kontrol("ambiyans girdileri 5 ve 6", "[5:a]" in f and "[6:a]" in f, f)
    kontrol("ambiyans ikinci parça gecikmeli", "adelay=delays=3700:all=1" in f, f)
    kontrol("ambiyans ikinci parça kendi yerinden kesilir", "atrim=start=3.700000" in f, f)
    kontrol("ambiyans kartta 4 sn söner", "d=4.000" in f, f)
    kontrol("ambiyans karışım", "amix=inputs=2:normalize=0" in f and f.endswith("[amb]"), f)
    kontrol("ambiyans video boyu", "atrim=end=12.000000[amb]" in f, f)
    b = birlestirme_komutu("klipler.txt", ["a.mp3"], "altyazi.ass", "fontlar", "X", "c.mp4",
                           ["dis.mp3"])
    kontrol("birleştirme döngülü girdi", b[b.index("dis.mp3") - 3:b.index("dis.mp3")] ==
            ["-stream_loop", "-1", "-i"], b)
    kontrol("birleştirme karışım çıkışı", b[b.index("-map", b.index("-map") + 1) + 1] == "[son]", b)
    kontrol("birleştirme ducking", "sidechaincompress" in " ".join(b))
    b = birlestirme_komutu("klipler.txt", ["a.mp3"], "altyazi.ass", "fontlar", "X", "c.mp4")
    kontrol("ambiyanssız çıkış [ses]", "[ses]" in b and "sidechaincompress" not in " ".join(b))


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
        _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=orange:s=1080x1080",
               "-frames:v", "1", str(klasor / "gorseller" / "secenek_A.png")])
        for mp3 in (klasor / "sesler").glob("s0*_c*.mp3"):
            _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                   "-t", "0.5", "-c:a", "libmp3lame", str(mp3)])
        cikti = montajla(veri, klasor, [2], {})
        kontrol("önizleme adı", cikti == klasor / "onizleme.mp4", cikti)
        sure = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(cikti)], capture_output=True, encoding="utf-8").stdout.strip())
        beklenen = round((0.5 * 2 + CUMLE_ARASI + SAHNE_SONU) * 30) / 30 + 4
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

        # ambiyanslı: 2 sn'lik ses dosyası döngüyle ~6 sn'lik videoyu doldurur, çıktı stereo
        amb = Path(tmp) / "ambiyans"
        amb.mkdir()
        _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
               "-c:a", "libmp3lame", str(amb / "otobus.mp3")])
        veri["sahneler"][1]["mekan"] = "otobus"
        cikti = montajla(veri, klasor, [2], {}, ambiyans_klasoru=amb)
        bilgi = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=channels:format=duration", "-of", "csv=p=0", str(cikti)],
            capture_output=True, encoding="utf-8").stdout.split()
        kontrol("ambiyanslı video stereo", bilgi[0].strip(",") == "2", bilgi)
        kontrol("ambiyanslı video süresi", abs(float(bilgi[-1]) - beklenen) < 0.15, bilgi)
        hacim = subprocess.run(
            [ffmpeg, "-v", "info", "-ss", "4.5", "-t", "1", "-i", str(cikti), "-af", "volumedetect",
             "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stderr
        kontrol("ambiyans kartta da duyulur", "mean_volume: -91" not in hacim and "mean_volume" in hacim,
                hacim[-300:])

        # kart okumalı ve kancalı: kart okuma bitene kadar uzar, ses -14 LUFS civarına gelir
        _uret([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
               "-c:a", "libmp3lame", str(klasor / "sesler" / "kart.mp3")])
        zamanlama = klasor / "sesler" / "zamanlama.json"
        kayitlar = json.loads(zamanlama.read_text(encoding="utf-8"))
        kayitlar["cumleler"]["kart"] = {
            "metin": "Teyze kayıp. Zarfı şimdi açacak mısın? A: Zarfı aç. B: Söz verdin, açma."}
        zamanlama.write_text(json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
        veri["kanca"] = "Yanındaki koltuk neden boş?"
        cikti = montajla(veri, klasor, [1, 2], {}, ambiyans_klasoru=amb)
        kontrol("tam bölüm adı", cikti == klasor / "video.mp4", cikti)
        sure = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(cikti)], capture_output=True, encoding="utf-8").stdout.strip())
        sahneler = 2 * round((0.5 * 2 + CUMLE_ARASI + SAHNE_SONU) * 30) / 30
        beklenen = sahneler + round((KART_SES_BAS + 5.0 + KART_SES_SONU) * 30) / 30
        kontrol("kart okumalı video süresi", abs(sure - beklenen) < 0.2, f"{sure} != {beklenen}")
        olcum = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostats", "-i", str(cikti), "-af",
             "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
            capture_output=True, encoding="utf-8", errors="replace").stderr
        olcum = olcumu_oku(olcum)
        kontrol("ses -14 LUFS civarı", olcum and abs(float(olcum["input_i"]) + 14) < 1.5, olcum)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for ad, fonk in list(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            fonk()
    print(f"{basarili} başarılı, {basarisiz} başarısız")
    sys.exit(1 if basarisiz else 0)
