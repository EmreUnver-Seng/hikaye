"""ses.py için testler.

Çalıştırma:  python kod/test_ses.py
Ek kütüphane gerekmez. ElevenLabs'e bağlanmaz: sahte bir istemci kullanılır,
bu yüzden hiç kredi harcanmaz.
"""

import base64
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

KOD = Path(__file__).resolve().parent
KOK = KOD.parent
sys.path.insert(0, str(KOD))

from elevenlabs.core.api_error import ApiError  # noqa: E402

from ses import (  # noqa: E402
    SES_HARITASI,
    SesHatasi,
    dosya_adi,
    eksik_sesler,
    hizalama_sec,
    isleri_hazirla,
    karakter_sayisi,
    kayitlari_yukle,
    kelimeleri_cikar,
    main,
    ses_haritasi_dogrula,
    ses_haritasi_yukle,
    etiketleri_ayikla,
    istek_metni,
    seslendir,
)

DENEME_GEORGE = KOK / "bolumler" / "bolum_01" / "sesler" / "deneme" / "anlatici_george_v4.json"
SAHTE_MP3 = b"ID3fake-mp3"


def hata_bekle(fonksiyon, *parcalar):
    try:
        fonksiyon()
    except SesHatasi as e:
        for parca in parcalar:
            assert parca in str(e), f"'{parca}' hata mesajında yok: {e}"
        return
    raise AssertionError("SesHatasi fırlatılmadı")


def ornek_harita(**degisiklik):
    harita = {"model": "eleven_v4",
              "sesler": {"anlatici": "ID_ANLATICI", "fatma": "ID_FATMA", "kerem": "ID_KEREM"}}
    harita.update(degisiklik)
    return harita


def ornek_veri():
    def sahne(no, karakterler, cumleler):
        return {"no": no, "gorsel": "x", "karakterler": karakterler,
                "cumleler": [{"konusan": k, "metin": m} for k, m in cumleler]}
    return {"bolum": 1, "baslik": "Kalkış", "sahneler": [
        sahne(1, [], [("anlatici", "Yanındaki koltuk boş."), ("anlatici", "Ama biri vardı.")]),
        sahne(2, ["fatma"], [("fatma", "Bunu al evladım.")]),
        sahne(3, ["kerem"], [("kerem", "Biletler lütfen!"), ("anlatici", "Hep acelesi var.")]),
    ], "ikilem": {"soru": "?", "secenekler": {"A": "a", "B": "b"}}}


def hizalama_uret(metin):
    """Her harfe 0,1 sn veren gerçek biçimli bir hizalama."""
    return {"characters": list(metin),
            "character_start_times_seconds": [i * 0.1 for i in range(len(metin))],
            "character_end_times_seconds": [(i + 1) * 0.1 for i in range(len(metin))]}


class SahteIstemci:
    """ElevenLabs istemcisinin ses.py'nin kullandığı kısmı."""

    def __init__(self, kullanilan=0, limit=10000, hata_sirasi=None):
        self.cagrilar = []
        self.hata_sirasi = hata_sirasi  # bu sıradaki çağrı (1'den) hata verir
        self.kullanilan, self.limit = kullanilan, limit
        self.text_to_speech = SimpleNamespace(convert_with_timestamps=self._seslendir)
        self.user = SimpleNamespace(subscription=SimpleNamespace(get=self._abonelik))

    def _seslendir(self, voice_id, **kw):
        self.cagrilar.append({"voice_id": voice_id, **kw})
        if self.hata_sirasi == len(self.cagrilar):
            raise ApiError(status_code=500, body={"detail": "sunucu hatası"})
        return SimpleNamespace(audio_base_64=base64.b64encode(SAHTE_MP3).decode(),
                               alignment=SimpleNamespace(**hizalama_uret(kw["text"])),
                               normalized_alignment=None)

    def _abonelik(self):
        return SimpleNamespace(character_count=self.kullanilan, character_limit=self.limit)


def sessiz(*_args, **_kw):
    pass


def calistir(klasor, istemci, cevap="e", **kw):
    """seslendir()'i sahte giriş/çıkışla çalıştırır; (çıkış kodu, çıktı metni) döner."""
    satirlar = []
    kod = seslendir(kw.pop("veri", None) or ornek_veri(), klasor, kw.pop("harita", ornek_harita()), istemci,
                    sor=lambda _soru: cevap, yaz=lambda *a: satirlar.append(" ".join(map(str, a))),
                    **kw)
    return kod, "\n".join(satirlar)


# --- Görev 1: ses eşlemesi ---

def test_harita_gecerli():
    h = ses_haritasi_yukle(SES_HARITASI)
    assert h["model"] == "eleven_v4", h
    assert h["sesler"]["murat"] == "5HEFEBb9WCCpCdgZE77B", h
    assert h["sesler"]["anlatici"] == "mF7tIc9VLrznhGooGjaT", h


def test_harita_hatalari():
    hata_bekle(lambda: ses_haritasi_dogrula({"sesler": {}}), "model")
    hata_bekle(lambda: ses_haritasi_dogrula({"model": "eleven_v4", "sesler": []}), "sesler")
    hata_bekle(lambda: ses_haritasi_dogrula(
        {"model": "eleven_v4", "sesler": {"rizaa": {"id": "x"}}}), "rizaa")
    hata_bekle(lambda: ses_haritasi_dogrula(
        {"model": "eleven_v4", "sesler": {"riza": {"id": " "}}}), "riza", "id")
    hata_bekle(lambda: ses_haritasi_dogrula([]), "nesne")
    # İki hata aynı anda: ikisi de listelenir.
    hata_bekle(lambda: ses_haritasi_dogrula(
        {"model": "", "sesler": {"ayla": {}}}), "model", "ayla")


def test_harita_dosya_yok():
    with tempfile.TemporaryDirectory() as d:
        hata_bekle(lambda: ses_haritasi_yukle(Path(d) / "yok.json"), "bulunamadı")
        bozuk = Path(d) / "bozuk.json"
        bozuk.write_text("{", encoding="utf-8")
        hata_bekle(lambda: ses_haritasi_yukle(bozuk), "JSON")


# --- Görev 2: kelime zamanlaması ---

def test_kelimeler_gercek():
    if not DENEME_GEORGE.exists():
        print("  (test_kelimeler_gercek atlandı: deneme dosyası yok)")
        return
    hizalama = json.loads(DENEME_GEORGE.read_text(encoding="utf-8"))["alignment"]
    k = kelimeleri_cikar(hizalama)
    assert len(k) == 11, [x["kelime"] for x in k]
    assert k[0]["kelime"] == "Yanındaki", k[0]
    assert k[2]["kelime"] == "boş.", k[2]
    onceki = -1
    for x in k:
        assert x["baslangic"] <= x["bitis"], x
        assert x["baslangic"] >= onceki, x
        onceki = x["baslangic"]


def test_coklu_bosluk():
    k = kelimeleri_cikar(hizalama_uret("  Ne  yapacaksın? "))
    assert [x["kelime"] for x in k] == ["Ne", "yapacaksın?"], k
    assert k[0] == {"kelime": "Ne", "baslangic": 0.2, "bitis": 0.4}, k[0]


def test_hizalama_yok():
    hata_bekle(lambda: hizalama_sec(SimpleNamespace(alignment=None, normalized_alignment=None)),
               "zamanlama")
    yedek = hizalama_uret("ab")
    assert hizalama_sec(SimpleNamespace(alignment=None, normalized_alignment=yedek)) == yedek
    assert hizalama_sec({"alignment": yedek}) == yedek


# --- Görev 3: iş listesi ---

def isler_ve_klasor(d, kayitlar=None, mp3ler=(), **kw):
    klasor = Path(d)
    for ad in mp3ler:
        (klasor / f"{ad}.mp3").write_bytes(SAHTE_MP3)
    return isleri_hazirla(ornek_veri(), kw.pop("harita", ornek_harita()), kayitlar or {},
                          klasor, **kw)


def kayit(metin, ses_id, model="eleven_v4"):
    return {"metin": metin, "ses_id": ses_id, "model": model}


def test_dosya_adi():
    assert dosya_adi(3, 2) == "s03_c2"
    assert dosya_adi(12, 1) == "s12_c1"


def test_hepsi_yeni():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d)
    assert [i.anahtar for i in isler] == ["s01_c1", "s01_c2", "s02_c1", "s03_c1", "s03_c2", "kart"]
    assert all(i.uret for i in isler)
    assert isler[2].ses_id == "ID_FATMA" and isler[2].konusan == "fatma"


def test_var_olan_atlanir():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s01_c1": kayit("Yanındaki koltuk boş.", "ID_ANLATICI")},
                                mp3ler=["s01_c1"])
    assert not isler[0].uret and isler[1].uret


def test_metin_degisince_yeniden():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s01_c1": kayit("Yanındaki koltuk dolu.", "ID_ANLATICI"),
                                    "s01_c2": kayit("Ama biri vardı.", "ID_ANLATICI")},
                                mp3ler=["s01_c1", "s01_c2"])
    assert isler[0].uret and not isler[1].uret


def test_ses_veya_model_degisince_yeniden():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s01_c1": kayit("Yanındaki koltuk boş.", "ESKI_ID"),
                                    "s01_c2": kayit("Ama biri vardı.", "ID_ANLATICI",
                                                    "eleven_flash_v2_5")},
                                mp3ler=["s01_c1", "s01_c2"])
    assert isler[0].uret and isler[1].uret


def test_mp3_silinmisse_yeniden():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s01_c1": kayit("Yanındaki koltuk boş.", "ID_ANLATICI")})
    assert isler[0].uret


def test_sahne_kapsami():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, sahne=3)
    assert [i.anahtar for i in isler] == ["s03_c1", "s03_c2"]


def test_cumle_zorla():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s03_c2": kayit("Hep acelesi var.", "ID_ANLATICI")},
                                mp3ler=["s03_c2"], cumle=(3, 2))
    assert [(i.anahtar, i.uret) for i in isler] == [("s03_c2", True)]


def test_olmayan_numara():
    with tempfile.TemporaryDirectory() as d:
        hata_bekle(lambda: isler_ve_klasor(d, sahne=99), "99")
        hata_bekle(lambda: isler_ve_klasor(d, cumle=(1, 9)), "1", "9")
        hata_bekle(lambda: isler_ve_klasor(d, cumle=(7, 1)), "7")


def test_eksik_sesler():
    harita = ornek_harita(sesler={"anlatici": "ID_ANLATICI"})
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, harita=harita)
    assert eksik_sesler(isler) == ["fatma", "kerem"], eksik_sesler(isler)
    assert isler[2].ses_id is None


def test_karakter_sayisi():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d, {"s01_c1": kayit("Yanındaki koltuk boş.", "ID_ANLATICI")},
                                mp3ler=["s01_c1"])
    beklenen = sum(len(m) for m in ["Ama biri vardı.", "Bunu al evladım.", "Biletler lütfen!",
                                     "Hep acelesi var.", "? A: a. B: b."])
    assert karakter_sayisi(isler) == beklenen, karakter_sayisi(isler)


def test_kart_okumasi():
    with tempfile.TemporaryDirectory() as d:
        isler = isler_ve_klasor(d)
        kart = isler[-1]
        assert (kart.anahtar, kart.konusan, kart.metin, kart.ses_id) == (
            "kart", "anlatici", "? A: a. B: b.", "ID_ANLATICI"), kart
        hazir = isler_ve_klasor(d, {"kart": kayit("? A: a. B: b.", "ID_ANLATICI")}, mp3ler=["kart"])
        assert not hazir[-1].uret, hazir[-1]
        yalniz = isler_ve_klasor(d, {"kart": kayit("? A: a. B: b.", "ID_ANLATICI")}, kart=True)
        assert [(i.anahtar, i.uret) for i in yalniz] == [("kart", True)], yalniz
        assert all(i.anahtar != "kart" for i in isler_ve_klasor(d, sahne=1))
        assert all(i.anahtar != "kart" for i in isler_ve_klasor(d, cumle=(1, 1)))


def test_bozuk_zamanlama():
    with tempfile.TemporaryDirectory() as d:
        assert kayitlari_yukle(Path(d)) == {}
        (Path(d) / "zamanlama.json").write_text("", encoding="utf-8")
        hata_bekle(lambda: kayitlari_yukle(Path(d)), "zamanlama.json")
        (Path(d) / "zamanlama.json").write_text("[]", encoding="utf-8")
        hata_bekle(lambda: kayitlari_yukle(Path(d)), "zamanlama.json")


# --- Görev 4: seslendirme akışı ---

def test_uretim_dosya_ve_kayit():
    with tempfile.TemporaryDirectory() as d:
        klasor = Path(d) / "sesler"
        istemci = SahteIstemci()
        kod, cikti = calistir(klasor, istemci)
        assert kod == 0, cikti
        assert len(istemci.cagrilar) == 6, istemci.cagrilar
        assert istemci.cagrilar[-1]["text"] == "? A: a. B: b.", istemci.cagrilar[-1]
        assert (klasor / "kart.mp3").read_bytes() == SAHTE_MP3
        c = istemci.cagrilar[2]
        assert c["voice_id"] == "ID_FATMA" and c["text"] == "Bunu al evladım.", c
        assert c["model_id"] == "eleven_v4" and c["language_code"] == "tr", c
        assert c["output_format"] == "mp3_44100_128", c
        assert (klasor / "s02_c1.mp3").read_bytes() == SAHTE_MP3
        veri = json.loads((klasor / "zamanlama.json").read_text(encoding="utf-8"))
        assert veri["bolum"] == 1, veri
        k = veri["cumleler"]["s02_c1"]
        assert {key: k[key] for key in ("sahne", "cumle", "konusan", "metin", "ses_id",
                                         "model", "dosya")} == {
            "sahne": 2, "cumle": 1, "konusan": "fatma", "metin": "Bunu al evladım.",
            "ses_id": "ID_FATMA", "model": "eleven_v4", "dosya": "s02_c1.mp3"}, k
        assert k["sure"] == 1.6, k["sure"]
        assert [x["kelime"] for x in k["kelimeler"]] == ["Bunu", "al", "evladım."]
        assert not (klasor / "zamanlama.json.tmp").exists()


def test_multilingual_dil_kodu_yok():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci()
        calistir(Path(d), istemci, harita=ornek_harita(model="eleven_multilingual_v2"))
        assert istemci.cagrilar and all("language_code" not in c for c in istemci.cagrilar)


def test_ikinci_calisma_atlar():
    with tempfile.TemporaryDirectory() as d:
        calistir(Path(d), SahteIstemci())
        istemci = SahteIstemci()
        kod, cikti = calistir(Path(d), istemci)
        assert kod == 0 and not istemci.cagrilar, cikti
        assert "Hepsi hazır" in cikti, cikti


def test_eksik_ses_api_cagrilmaz():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci()
        kod, cikti = calistir(Path(d), istemci,
                              harita=ornek_harita(sesler={"anlatici": "ID_ANLATICI"}))
        assert kod == 1 and not istemci.cagrilar, cikti
        assert "kerem" in cikti and "fatma" in cikti and "sesler.json" in cikti, cikti


def test_kota_yetmezse_cagrilmaz():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci(kullanilan=9990, limit=10000)
        kod, cikti = calistir(Path(d), istemci)
        assert kod == 1 and not istemci.cagrilar, cikti
        assert "kota" in cikti.lower(), cikti


def test_hayir_cevabi():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci()
        kod, cikti = calistir(Path(d), istemci, cevap="h")
        assert kod == 0 and not istemci.cagrilar, cikti
        assert not (Path(d) / "zamanlama.json").exists()


def test_kuru_cagrilmaz():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci(kullanilan=581)
        kod, cikti = calistir(Path(d), istemci, kuru=True,
                              cevap=None)  # soru sorulursa None döner ve test bozulur
        assert kod == 0 and not istemci.cagrilar, cikti
        assert "6 cümle" in cikti and "9419" in cikti, cikti


def test_kuru_anahtarsiz():
    with tempfile.TemporaryDirectory() as d:
        kod, cikti = calistir(Path(d), None, kuru=True)
        assert kod == 0, cikti
        assert "bilinmiyor" in cikti and "6 cümle" in cikti, cikti
        hata_bekle(lambda: calistir(Path(d), None), "ELEVENLABS_API_KEY")


def test_yarida_hata_kayit_korunur():
    with tempfile.TemporaryDirectory() as d:
        istemci = SahteIstemci(hata_sirasi=3)
        hata_bekle(lambda: calistir(Path(d), istemci), "500")
        kayitlar = kayitlari_yukle(Path(d))
        assert sorted(kayitlar) == ["s01_c1", "s01_c2"], kayitlar
        istemci = SahteIstemci()
        kod, _ = calistir(Path(d), istemci)
        assert kod == 0 and len(istemci.cagrilar) == 4, istemci.cagrilar


def test_api_hata_mesajlari():
    for durum, govde, parca in [(401, {"detail": {"status": "invalid_api_key"}}, "anahtar"),
                                (401, {"detail": {"status": "quota_exceeded"}}, "kota"),
                                (404, {"detail": {"status": "voice_not_found"}}, "sesler.json")]:
        class Hatali(SahteIstemci):
            def _seslendir(self, voice_id, **kw):
                raise ApiError(status_code=durum, body=govde)
        with tempfile.TemporaryDirectory() as d:
            hata_bekle(lambda: calistir(Path(d), Hatali()), parca)


def test_ekleme_var_olan_sesi_yeniden_kullanir():
    """Sahnenin başına cümle eklenince kayan cümleler yeniden ücretlenmez."""
    with tempfile.TemporaryDirectory() as d:
        klasor = Path(d)
        calistir(klasor, SahteIstemci())  # 5 cümle hazır
        eski_c1 = b"ses-bir"
        eski_c2 = b"ses-iki"
        (klasor / "s01_c1.mp3").write_bytes(eski_c1)
        (klasor / "s01_c2.mp3").write_bytes(eski_c2)
        veri = ornek_veri()
        veri["sahneler"][0]["cumleler"].insert(0, {"konusan": "anlatici", "metin": "Yeni cümle."})
        istemci = SahteIstemci()
        kod, cikti = calistir(klasor, istemci, veri=veri)
        assert kod == 0, cikti
        assert [c["text"] for c in istemci.cagrilar] == ["Yeni cümle."], istemci.cagrilar
        assert (klasor / "s01_c2.mp3").read_bytes() == eski_c1
        assert (klasor / "s01_c3.mp3").read_bytes() == eski_c2
        kayitlar = kayitlari_yukle(klasor)
        assert kayitlar["s01_c3"]["metin"] == "Ama biri vardı.", kayitlar["s01_c3"]
        assert kayitlar["s01_c3"]["cumle"] == 3 and kayitlar["s01_c3"]["dosya"] == "s01_c3.mp3"
        assert "11 karakter" in cikti, cikti  # yalnızca "Yeni cümle."


def test_cumle_zorla_yeniden_kullanmaz():
    with tempfile.TemporaryDirectory() as d:
        calistir(Path(d), SahteIstemci())
        istemci = SahteIstemci()
        calistir(Path(d), istemci, cumle=(1, 1))
        assert len(istemci.cagrilar) == 1, istemci.cagrilar


def test_bos_hizalama_hata():
    bos = {"characters": [], "character_start_times_seconds": [],
           "character_end_times_seconds": []}
    hata_bekle(lambda: hizalama_sec(SimpleNamespace(alignment=SimpleNamespace(**bos),
                                                    normalized_alignment=None)), "zamanlama")


def test_onayda_iptal():
    for istisna in (KeyboardInterrupt, EOFError):
        def sor(_soru, istisna=istisna):
            raise istisna
        with tempfile.TemporaryDirectory() as d:
            istemci = SahteIstemci()
            kod = seslendir(ornek_veri(), Path(d), ornek_harita(), istemci, sor=sor, yaz=sessiz)
            assert kod == 0 and not istemci.cagrilar, istisna


def test_cli_arguman_hatalari():
    senaryo = str(KOK / "bolumler" / "bolum_01" / "senaryo.json")
    for argv in ([senaryo, "--cumle", "3"], [senaryo, "--cumle", "a.b"],
                 [senaryo, "--sahne", "1", "--cumle", "1.1"]):
        try:
            kod = main(argv)
        except SystemExit as e:
            kod = e.code
        assert kod not in (0, None), argv


# --- Ton etiketi, bağlam ve hız (2026-11-28) ---

def ton_veri():
    v = ornek_veri()
    v["sahneler"][1]["cumleler"][0]["ton"] = "worried"
    return v


def test_harita_hiz():
    h = ses_haritasi_dogrula({"model": "eleven_v4", "sesler": {}})
    assert h["hiz"] == 1.0, h
    assert ses_haritasi_dogrula({"model": "eleven_v4", "sesler": {}, "hiz": 1.2})["hiz"] == 1.2
    for kotu in (1.5, 0.5, "1.2", True):
        hata_bekle(lambda k=kotu: ses_haritasi_dogrula(
            {"model": "eleven_v4", "sesler": {}, "hiz": k}), "hiz")
    assert ses_haritasi_yukle(SES_HARITASI)["hiz"] == 1.2


def test_istek_metni():
    assert istek_metni("Bak.", None) == "Bak."
    assert istek_metni("Bak.", " impatient ") == "[impatient] Bak."


def test_etiketler_ayiklanir():
    h = etiketleri_ayikla(hizalama_uret("[worried] Bunu al."))
    assert "".join(h["characters"]) == "Bunu al.", h["characters"]
    k = kelimeleri_cikar(h)
    assert [x["kelime"] for x in k] == ["Bunu", "al."], k
    assert k[0]["baslangic"] == 1.0, k[0]  # zamanlar kaymaz: 'B' 10. harf
    assert etiketleri_ayikla(hizalama_uret("Düz cümle."))["characters"] == list("Düz cümle.")


def test_komsu_cumleler_ve_ton():
    with tempfile.TemporaryDirectory() as d:
        isler = isleri_hazirla(ton_veri(), ornek_harita(), {}, Path(d))
    ilk, ikinci, fatma = isler[0], isler[1], isler[2]
    assert ilk.onceki is None and ilk.sonraki == "Ama biri vardı.", ilk
    assert fatma.onceki == "Ama biri vardı." and fatma.sonraki == "Biletler lütfen!", fatma
    assert fatma.ton == "worried" and ilk.ton is None
    assert isler[-1].anahtar == "kart" and isler[-1].onceki is None
    # Sahne kapsamında da komşular bölüm sırasından gelir.
    with tempfile.TemporaryDirectory() as d:
        tek = isleri_hazirla(ton_veri(), ornek_harita(), {}, Path(d), sahne=2)
    assert tek[0].onceki == "Ama biri vardı." and tek[0].sonraki == "Biletler lütfen!"


def test_ton_degisince_yeniden_hiz_yoksa_hazir():
    with tempfile.TemporaryDirectory() as d:
        k = {"s02_c1": kayit("Bunu al evladım.", "ID_FATMA"),       # eski kayıt: ton/hiz yok
             "s01_c1": kayit("Yanındaki koltuk boş.", "ID_ANLATICI")}
        isler = isleri_hazirla(ton_veri(), ornek_harita(hiz=1.2), k, Path(d))
        for ad in ("s02_c1", "s01_c1"):
            (Path(d) / f"{ad}.mp3").write_bytes(SAHTE_MP3)
        isler = isleri_hazirla(ton_veri(), ornek_harita(hiz=1.2), k, Path(d))
    by = {i.anahtar: i for i in isler}
    assert by["s02_c1"].uret, "ton eklenen cümle yeniden üretilmeli"
    assert not by["s01_c1"].uret, "hiz alanı olmayan eski kayıt hazır sayılmalı"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "s01_c1.mp3").write_bytes(SAHTE_MP3)
        k = {"s01_c1": {**kayit("Yanındaki koltuk boş.", "ID_ANLATICI"), "hiz": 1.0}}
        isler = isleri_hazirla(ornek_veri(), ornek_harita(hiz=1.2), k, Path(d))
    assert isler[0].uret, "farklı hızla üretilmiş kayıt yeniden üretilmeli"


def test_karakter_sayisi_etiket_dahil():
    with tempfile.TemporaryDirectory() as d:
        isler = isleri_hazirla(ton_veri(), ornek_harita(), {}, Path(d), sahne=2)
    assert karakter_sayisi(isler) == len("[worried] Bunu al evladım."), karakter_sayisi(isler)


def test_seslendir_istek_ve_kayit():
    istemci = SahteIstemci()
    with tempfile.TemporaryDirectory() as d:
        kod, cikti = calistir(d, istemci, veri=ton_veri(), harita=ornek_harita(hiz=1.2))
        kayitlar = kayitlari_yukle(d)
    assert kod == 0, cikti
    fatma = next(c for c in istemci.cagrilar if c["voice_id"] == "ID_FATMA")
    assert fatma["text"] == "[worried] Bunu al evladım.", fatma
    assert fatma["voice_settings"] == {"speed": 1.2}, fatma
    assert fatma["previous_text"] == "Ama biri vardı." and fatma["next_text"] == "Biletler lütfen!"
    ilk = istemci.cagrilar[0]
    assert "previous_text" not in ilk and ilk["next_text"] == "Ama biri vardı.", ilk
    k = kayitlar["s02_c1"]
    assert k["ton"] == "worried" and k["hiz"] == 1.2, k
    assert [x["kelime"] for x in k["kelimeler"]] == ["Bunu", "al", "evladım."], k["kelimeler"]
    assert k["metin"] == "Bunu al evladım."


def test_hiz_varsayilanda_ayar_gitmez():
    istemci = SahteIstemci()
    with tempfile.TemporaryDirectory() as d:
        calistir(d, istemci)
    assert all("voice_settings" not in c for c in istemci.cagrilar), istemci.cagrilar[0]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    testler = [(ad, f) for ad, f in sorted(globals().items())
               if ad.startswith("test_")]
    basarisiz = 0
    for ad, f in testler:
        try:
            f()
        except Exception as e:  # noqa: BLE001
            basarisiz += 1
            print(f"BAŞARISIZ  {ad}: {type(e).__name__}: {e}")
    if basarisiz:
        print(f"\n{basarisiz}/{len(testler)} test başarısız.")
        sys.exit(1)
    print(f"Tüm testler geçti ({len(testler)}).")
