"""senaryo.py için testler.

Çalıştırma:  python kod/test_senaryo.py
Ek kütüphane gerekmez. Her test geçerli bir örneği bozar ve
doğrulayıcının bu bozukluğu yakaladığını kontrol eder.
"""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

KOD = Path(__file__).resolve().parent
sys.path.insert(0, str(KOD))

from senaryo import (SenaryoHatasi, dogrula, kart_okuma_metni,  # noqa: E402
                     secenek_gorseli, secenek_metni, senaryo_yukle)


def gecerli_ornek(bolum=1):
    """8 sahneli, ~60 sn'lik geçerli bir senaryo."""
    sahneler = []
    for no in range(1, 9):
        sahneler.append({
            "no": no,
            "gorsel": f"Sahne {no}: gece otobüsünün içi, mor-mavi ışık.",
            "mekan": "otobus",
            "karakterler": ["sen", "fatma"],
            "cumleler": [
                {"konusan": "anlatici",
                 "metin": "Otobüs karanlık yolda ilerliyor ve sen camdan dışarı bakıyorsun."},
                {"konusan": "fatma",
                 "metin": "Bu yolu çok iyi bilirim evladım, çok iyi."},
            ],
        })
    veri = {"bolum": bolum, "baslik": "Kalkış", "sahneler": sahneler,
            "ikilem": {"soru": "Zarfı açacak mısın?",
                       "secenekler": {"A": "Zarfı aç", "B": "Açma"}}}
    if bolum >= 2:
        veri["kanca"] = "Bir yolcu nasıl kaybolur?"  # Bölüm 2+ zorunlu
    if bolum == 8:
        del veri["ikilem"]["secenekler"]
    return veri


def hata_icerir(veri, parca, klasor_adi=None):
    hatalar, _ = dogrula(veri, klasor_adi)
    assert any(parca in h for h in hatalar), f"'{parca}' beklenen hata yok. Hatalar: {hatalar}"


def uyari_icerir(veri, parca):
    hatalar, uyarilar = dogrula(veri)
    assert not hatalar, f"Beklenmeyen hata: {hatalar}"
    assert any(parca in u for u in uyarilar), f"'{parca}' beklenen uyarı yok. Uyarılar: {uyarilar}"


def bozuk(degistir, bolum=1):
    veri = gecerli_ornek(bolum)
    degistir(veri)
    return veri


# --- Geçerli ---------------------------------------------------------------

def test_gecerli():
    hatalar, uyarilar = dogrula(gecerli_ornek())
    assert hatalar == [] and uyarilar == [], (hatalar, uyarilar)


def test_gecerli_bolum8_seceneksiz():
    hatalar, _ = dogrula(gecerli_ornek(8))
    assert hatalar == [], hatalar


def test_bos_karakter_listesi_anlaticiyla_gecerli():
    def d(v):
        v["sahneler"][0]["karakterler"] = []
        v["sahneler"][0]["cumleler"] = [v["sahneler"][0]["cumleler"][0]]
    hatalar, _ = dogrula(bozuk(d))
    assert hatalar == [], hatalar


# --- Kök alanlar -----------------------------------------------------------

def test_kok_nesne_degil():
    hata_icerir([1, 2], "nesne")


def test_eksik_baslik():
    hata_icerir(bozuk(lambda v: v.pop("baslik")), "baslik")


def test_bos_baslik():
    hata_icerir(bozuk(lambda v: v.update(baslik="  ")), "baslik")


def test_kanca_istege_bagli():
    hatalar, uyarilar = dogrula(bozuk(lambda v: v.update(kanca="Yanındaki koltuk neden boş?")))
    assert hatalar == [] and uyarilar == [], (hatalar, uyarilar)
    hata_icerir(bozuk(lambda v: v.update(kanca="")), "kanca")
    hata_icerir(bozuk(lambda v: v.update(kanca=3)), "kanca")
    uyari_icerir(bozuk(lambda v: v.update(kanca="bir iki üç dört beş altı yedi")), "kanca")


def test_kart_okuma_metni():
    assert kart_okuma_metni({"soru": "Ne yapacaksın?", "secenekler": {
        "A": "Zarfı aç", "B": {"metin": "Söz verdin, açma.", "gorsel": "x"}}}) ==         "Ne yapacaksın? A: Zarfı aç. B: Söz verdin, açma."
    assert kart_okuma_metni({"soru": "Sence ne oldu?"}) == "Sence ne oldu?"


def test_bilinmeyen_alan():
    hata_icerir(bozuk(lambda v: v.update(baslk="x")), "baslk")


def test_bilinmeyen_alan_cumlede():
    hata_icerir(bozuk(lambda v: v["sahneler"][0]["cumleler"][0].update(metn="x")), "metn")


def test_bolum_aralik_disi():
    hata_icerir(bozuk(lambda v: v.update(bolum=9)), "bolum")


def test_bolum_bool():
    hata_icerir(bozuk(lambda v: v.update(bolum=True)), "bolum")


def test_klasor_numarasi_uyusmuyor():
    hata_icerir(gecerli_ornek(), "bolum_02", klasor_adi="bolum_02")


# --- Sahneler --------------------------------------------------------------

def test_az_sahne():
    hata_icerir(bozuk(lambda v: v["sahneler"].pop()), "8")


def test_cok_sahne():
    def d(v):
        for no in range(9, 14):
            s = copy.deepcopy(v["sahneler"][0])
            s["no"] = no
            v["sahneler"].append(s)
    hata_icerir(bozuk(d), "12")


def test_sahneler_liste_degil():
    hata_icerir(bozuk(lambda v: v.update(sahneler={"1": {}})), "sahneler")


def test_no_sirasi_bozuk():
    hata_icerir(bozuk(lambda v: v["sahneler"][2].update(no=5)), "sahne 3, no")


def test_bilinmeyen_karakter():
    hata_icerir(bozuk(lambda v: v["sahneler"][1]["karakterler"].append("hasan")), "hasan")


def test_tekrarli_karakter():
    hata_icerir(bozuk(lambda v: v["sahneler"][1]["karakterler"].append("sen")), "birden fazla")


def test_konusan_sahnede_yok():
    hata_icerir(bozuk(lambda v: v["sahneler"][3]["cumleler"][1].update(konusan="kerem")),
                "sahne 4, cümle 2, konusan")


def test_bos_metin():
    hata_icerir(bozuk(lambda v: v["sahneler"][0]["cumleler"][0].update(metin="")), "metin")


def test_bos_cumleler():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].update(cumleler=[])), "cumleler")


def test_cumleler_string():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].update(cumleler="Merhaba")), "cumleler")


def test_bos_gorsel():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].update(gorsel="")), "gorsel")


# --- İkilem ----------------------------------------------------------------

def test_ikilem_soru_eksik():
    hata_icerir(bozuk(lambda v: v["ikilem"].pop("soru")), "soru")


def test_secenekler_eksik():
    hata_icerir(bozuk(lambda v: v["ikilem"].pop("secenekler"), bolum=3), "secenekler")


def test_secenek_C_var():
    hata_icerir(bozuk(lambda v: v["ikilem"]["secenekler"].update(C="x"), bolum=3), "C")


def test_bos_secenek():
    hata_icerir(bozuk(lambda v: v["ikilem"]["secenekler"].update(B="")), "secenekler.B")


def test_bolum8_secenek_var():
    hata_icerir(bozuk(lambda v: v["ikilem"].update(secenekler={"A": "x", "B": "y"}), bolum=8),
                "secenekler")


# --- Uyarılar --------------------------------------------------------------

def test_uyari_cok_sen():
    def d(v):
        for s in v["sahneler"][:4]:
            s["cumleler"].append({"konusan": "sen", "metin": "Kimse yok mu?"})
    uyari_icerir(bozuk(d), "sen")


def test_uyari_uzun_cumle():
    uzun = " ".join(["kelime"] * 26)
    uyari_icerir(bozuk(lambda v: v["sahneler"][0]["cumleler"][0].update(metin=uzun)), "26 kelime")


def test_uyari_kisa_sure():
    def d(v):
        for s in v["sahneler"]:
            s["cumleler"] = [{"konusan": "anlatici", "metin": "Gece."}]
    uyari_icerir(bozuk(d), "sn")


# --- Dosya ve komut satırı ------------------------------------------------

def calistir(*argumanlar):
    return subprocess.run([sys.executable, str(KOD / "senaryo.py"), *argumanlar],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_gecerli_dosya():
    with tempfile.TemporaryDirectory() as d:
        yol = Path(d) / "bolum_01" / "senaryo.json"
        yol.parent.mkdir()
        yol.write_text(json.dumps(gecerli_ornek(), ensure_ascii=False), encoding="utf-8")
        s = calistir(str(yol))
        assert s.returncode == 0, s.stdout + s.stderr
        assert "geçerli" in s.stdout, s.stdout


def test_cli_bozuk_json():
    with tempfile.TemporaryDirectory() as d:
        yol = Path(d) / "senaryo.json"
        yol.write_text('{"bolum": 1,\n "baslik": "x"\n "sahneler": []}', encoding="utf-8")
        s = calistir(str(yol))
        assert s.returncode == 1, s.stdout + s.stderr
        assert "satır 3" in s.stdout, s.stdout
        assert "Traceback" not in s.stderr, s.stderr


def test_cli_cok_buyuk_sayi_cokmez():
    with tempfile.TemporaryDirectory() as d:
        yol = Path(d) / "senaryo.json"
        yol.write_text('{"bolum": ' + "9" * 5000 + "}", encoding="utf-8")
        s = calistir(str(yol))
        assert s.returncode == 1 and "Traceback" not in s.stderr, s.stdout + s.stderr
        assert "JSON okunamadı" in s.stdout, s.stdout


def test_cli_dosya_yok():
    s = calistir("olmayan/senaryo.json")
    assert s.returncode == 1 and "bulunamadı" in s.stdout, s.stdout + s.stderr


def test_cli_klasor_verilmis():
    s = calistir(str(KOD))
    assert s.returncode == 1 and "klasör" in s.stdout, s.stdout + s.stderr


def test_cli_arguman_yok():
    s = calistir()
    assert s.returncode == 1 and "Kullanım" in s.stdout, s.stdout + s.stderr


def test_cli_hatali_senaryo_konumlu():
    with tempfile.TemporaryDirectory() as d:
        yol = Path(d) / "senaryo.json"
        veri = bozuk(lambda v: v["sahneler"][3]["cumleler"][1].update(konusan="kerem"))
        yol.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        s = calistir(str(yol))
        assert s.returncode == 1 and "sahne 4, cümle 2, konusan" in s.stdout, s.stdout


def test_senaryo_yukle_firlatir():
    with tempfile.TemporaryDirectory() as d:
        yol = Path(d) / "senaryo.json"
        yol.write_text(json.dumps({"bolum": 1}), encoding="utf-8")
        try:
            senaryo_yukle(yol)
        except SenaryoHatasi as e:
            assert e.hatalar
        else:
            raise AssertionError("SenaryoHatasi fırlatılmadı")


def test_mekan_bilinmeyen_deger():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].update(mekan="uzay")), "mekan")


def test_mekan_yazi_olmali():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].update(mekan=3)), "mekan")


def test_mekan_eksikse_uyari():
    uyari_icerir(bozuk(lambda v: v["sahneler"][2].pop("mekan")), "sahne 3")
    uyari_icerir(bozuk(lambda v: v["sahneler"][2].pop("mekan")), "mekan")


def test_mekan_gecerli_degerler():
    for m in ("otobus", "tesis", "istasyon", "dis"):
        hatalar, _ = dogrula(bozuk(lambda v, m=m: v["sahneler"][0].update(mekan=m)))
        assert hatalar == [], (m, hatalar)


def _gorselli(v, b=None):
    v["ikilem"]["secenekler"]["A"] = {"metin": "Zarfı aç", "gorsel": "Açılmış zarf"}
    if b is not None:
        v["ikilem"]["secenekler"]["B"] = b


def test_secenek_nesne_gecerli():
    hatalar, _ = dogrula(bozuk(lambda v: _gorselli(v, {"metin": "Açma"})))
    assert hatalar == [], hatalar


def test_secenek_nesne_metin_eksik():
    hata_icerir(bozuk(lambda v: _gorselli(v, {"gorsel": "Zarf"})), "secenekler.B")
    hata_icerir(bozuk(lambda v: _gorselli(v, {"gorsel": "Zarf"})), "'metin'")


def test_secenek_nesne_bos_metin():
    hata_icerir(bozuk(lambda v: _gorselli(v, {"metin": " "})), "secenekler.B.metin")


def test_secenek_nesne_bos_gorsel():
    hata_icerir(bozuk(lambda v: _gorselli(v, {"metin": "Açma", "gorsel": ""})),
                "secenekler.B.gorsel")


def test_secenek_nesne_bilinmeyen_alan():
    hata_icerir(bozuk(lambda v: _gorselli(v, {"metin": "Açma", "resim": "x"})), "resim")


def test_secenek_sayi_olamaz():
    hata_icerir(bozuk(lambda v: _gorselli(v, 5)), "secenekler.B")


def test_secenek_yardimcilari():
    assert secenek_metni("Aç") == "Aç" and secenek_gorseli("Aç") is None
    assert secenek_metni({"metin": "Aç", "gorsel": "zarf"}) == "Aç"
    assert secenek_gorseli({"metin": "Aç", "gorsel": "zarf"}) == "zarf"
    assert secenek_gorseli({"metin": "Aç"}) is None


# --- Saat animasyonu (sahne, isteğe bağlı) ---------------------------------

def _saatli(degisiklik=None, sil=None):
    """Sahne 2'ye geçerli bir 'saat' ekler; değişiklik/silme uygulanır."""
    def d(v):
        saat = {"bas": "02:45", "bit": "23:30", "yon": "geri", "cumle": 2, "kelime": "iyi."}
        saat.update(degisiklik or {})
        for alan in sil or ():
            del saat[alan]
        v["sahneler"][1]["saat"] = saat
    return bozuk(d)


def test_saat_gecerli():
    hatalar, uyarilar = dogrula(_saatli())
    assert not hatalar, hatalar
    assert not any("saat" in u for u in uyarilar), uyarilar
    assert not dogrula(_saatli({"es": 1.5, "kelime": "Bu", "cumle": 2}))[0]


def test_saat_kelime_noktalamasiz_ve_buyuk_harf_eslesir():
    assert not dogrula(_saatli({"kelime": "İYİ"}))[0]
    assert not dogrula(_saatli({"cumle": 1, "kelime": "otobüs"}))[0]


def test_saat_eksik_alan():
    hata_icerir(_saatli(sil=["yon"]), "'yon' alanı eksik")


def test_saat_bilinmeyen_alan():
    hata_icerir(_saatli({"hiz": 2}), "bilinmeyen alan")


def test_saat_bicimi():
    hata_icerir(_saatli({"bas": "2:45"}), "saat, bas")
    hata_icerir(_saatli({"bit": "24:00"}), "SS:DD")
    hata_icerir(_saatli({"bas": 245}), "saat, bas")


def test_saat_ayni():
    hata_icerir(_saatli({"bit": "02:45"}), "aynı")


def test_saat_yon():
    hata_icerir(_saatli({"yon": "sola"}), "geri, ileri")


def test_saat_cumle_yok():
    hata_icerir(_saatli({"cumle": 3}), "cumle")
    hata_icerir(_saatli({"cumle": True}), "cumle")


def test_saat_kelime_cumlede_yok():
    hata_icerir(_saatli({"kelime": "tesis"}), "'tesis' kelimesi")


def test_saat_es():
    hata_icerir(_saatli({"es": -1}), "saat, es")
    hata_icerir(_saatli({"es": 9}), "saat, es")
    hata_icerir(_saatli({"es": "1"}), "saat, es")


def test_saat_nesne_olmali():
    hata_icerir(bozuk(lambda v: v["sahneler"][0].__setitem__("saat", "02:45")), "saat")


def test_ton_istege_bagli():
    def ton(deger):
        return lambda v: v["sahneler"][0]["cumleler"][0].update(ton=deger)
    hatalar, uyarilar = dogrula(bozuk(ton("impatient, slightly annoyed")))
    assert hatalar == [] and uyarilar == [], (hatalar, uyarilar)
    hata_icerir(bozuk(ton("")), "ton")
    hata_icerir(bozuk(ton(3)), "ton")
    hata_icerir(bozuk(ton("[whispers]")), "köşeli")
    uyari_icerir(bozuk(ton("very very slow and quiet and sad")), "ton")
    hata_icerir(bozuk(lambda v: v["sahneler"][0]["cumleler"][0].update(metin="[sighs] Ah.")),
                "etiket")


def test_kanca_bolum2den_itibaren_zorunlu():
    hata_icerir(bozuk(lambda v: v.pop("kanca"), bolum=3), "zorunlu")
    hatalar, _ = dogrula(gecerli_ornek(1))
    assert hatalar == [], hatalar  # Bölüm 1'de kanca yok, yayınlandı ve değişmiyor
    hatalar, _ = dogrula(gecerli_ornek(2))
    assert hatalar == [], hatalar


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    testler = [(ad, f) for ad, f in sorted(globals().items()) if ad.startswith("test_")]
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
