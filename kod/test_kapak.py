"""kapak.py testleri (render yok). Çalıştır: python kod/test_kapak.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kapak import KapakHatasi, ass_metni, gorsel_sec, onceki_secim, seri_adi, tr_buyuk  # noqa: E402

basarili = basarisiz = 0


def kontrol(ad, kosul):
    global basarili, basarisiz
    if kosul:
        basarili += 1
    else:
        basarisiz += 1
        print(f"BAŞARISIZ: {ad}")


kontrol("tr_buyuk i/ı", tr_buyuk("kalkış ilk") == "KALKIŞ İLK")
kontrol("seri adı", seri_adi("# Son Durak\n\n## Tür") == "Son Durak")
try:
    seri_adi("başlıksız")
    kontrol("seri adı yoksa hata", False)
except KapakHatasi:
    kontrol("seri adı yoksa hata", True)

durum = {"bolumler": {"1": {"kazanan": "B"}}}
kontrol("önceki seçim", onceki_secim(durum, 2) == "B")
kontrol("önceki seçim yok", onceki_secim(durum, 3) is None)
kontrol("durum yok", onceki_secim(None, 2) is None)

kontrol("görsel varsayılan", gorsel_sec(None) == (1, "a"))
kontrol("görsel 4=b", gorsel_sec("4=b") == (4, "b"))
try:
    gorsel_sec("4b")
    kontrol("görsel hatalı", False)
except KapakHatasi:
    kontrol("görsel hatalı", True)

ass1 = ass_metni("Son Durak", 1, "Kalkış")
kontrol("bölüm no", "BÖLÜM 1" in ass1)
kontrol("toplam bölüm sayısı yok (sürpriz kaçmasın)", "/ 8" not in ass1)
kontrol("başlık büyük", "KALKIŞ" in ass1)
kontrol("bölüm 1'de seçim satırı yok", "Seçilen yol" not in ass1)
ass2 = ass_metni("Son Durak", 2, "Kimse hatırlamıyor", ("A", "Zarfı aç"))
kontrol("seçim satırı", "Seçilen yol" in ass2 and "Zarfı aç" in ass2)
kontrol("süslü parantez temizlenir", "{x}" not in ass_metni("S", 1, "{x}"))

print(f"{basarili}/{basarili + basarisiz} başarılı")
sys.exit(1 if basarisiz else 0)
