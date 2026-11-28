"""yeni_bolum.py testleri (API/ffmpeg yok). Çalıştır: python kod/test_yeni_bolum.py"""

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yeni_bolum as yb  # noqa: E402

basarili = basarisiz = 0


def kontrol(ad, kosul):
    global basarili, basarisiz
    if kosul:
        basarili += 1
    else:
        basarisiz += 1
        print(f"BAŞARISIZ: {ad}")


def girdiler(*cevaplar):
    kalan = list(cevaplar)
    return lambda _metin="": kalan.pop(0)


kontrol("boş = sistem", yb.secim_cozumle("") == "sistem")
kontrol("s", yb.secim_cozumle(" S ") == "sistem")
kontrol("k", yb.secim_cozumle("kendim") == "kendim")
kontrol("a", yb.secim_cozumle("a") == "atla")
kontrol("geçersiz", yb.secim_cozumle("x") is None)

durumlar = {k: "" for k, _ in yb.ADIMLAR}
with redirect_stdout(io.StringIO()) as cikti:
    secimler = yb.secimleri_sor(durumlar, girdiler("x", "k", "", "a", "s"))
kontrol("seçimler sırayla", secimler == {"gorsel": "kendim", "ses": "sistem",
                                         "montaj": "atla", "kapak": "sistem"})
kontrol("geçersizde yeniden sorar", "s, k ya da a" in cikti.getvalue())

try:
    yb.sor("?", girdiler("dur"))
    kontrol("dur durdurur", False)
except yb.Durdur:
    kontrol("dur durdurur", True)

veri = {"sahneler": [{"no": 1, "cumleler": [{}, {}]}, {"no": 2, "cumleler": [{}]}]}
with tempfile.TemporaryDirectory() as gecici:
    klasor = Path(gecici)
    (klasor / "gorseller").mkdir()
    (klasor / "sesler").mkdir()
    (klasor / "gorseller" / "sahne1_a.png").write_bytes(b"")
    (klasor / "gorseller" / "sahne2_b.png").write_bytes(b"")
    (klasor / "sesler" / "s01_c1.mp3").write_bytes(b"")
    d = yb.adim_durumlari(veri, klasor)
    kontrol("görsel durumu", d["gorsel"].startswith("1/2"))
    kontrol("ses durumu", d["ses"].startswith("1/3"))
    kontrol("video yok", d["montaj"] == "video.mp4 yok")
    kontrol("eksik sahneler", yb.eksik_sahneler(veri, klasor / "gorseller") == [2])
    kontrol("ek varyantlar", yb.ek_varyantlar(veri, klasor / "gorseller") == {2: ["b"]})

kontrol("komut metni", yb.komut_metni("ses", yb.KOK / "bolumler/bolum_01/senaryo.json", "--kuru")
        == "python kod/ses.py bolumler/bolum_01/senaryo.json --kuru")

# Uçtan uca: hepsi atla → yalnızca senaryo doğrulanır, başka bir şey çalışmaz.
senaryo = yb.KOK / "bolumler" / "bolum_01" / "senaryo.json"
if senaryo.exists():
    with redirect_stdout(io.StringIO()) as cikti:
        sonuc = yb.main([str(senaryo)], girdiler("a", "a", "a", "a"))
    kontrol("hepsi atla → başarılı", sonuc == 0)
    # 'kendim' → komut gösterilir, Enter bekler; 'dur' ile çıkılır.
    with redirect_stdout(io.StringIO()) as cikti:
        sonuc = yb.main([str(senaryo)], girdiler("k", "a", "a", "a", "dur"))
    kontrol("kendim → komut gösterilir", "kod/gorsel.py" in cikti.getvalue())
    kontrol("dur → 1 döner", sonuc == 1)

print(f"{basarili}/{basarili + basarisiz} başarılı")
sys.exit(1 if basarisiz else 0)
