"""Senaryo dosyasını (senaryo.json) doğrular.

Kullanım:
    python kod/senaryo.py bolumler/bolum_01/senaryo.json

Diğer modüllerden:
    from senaryo import senaryo_yukle
    veri = senaryo_yukle(Path("bolumler/bolum_01/senaryo.json"))

Şemanın açıklaması: docs/superpowers/specs/2026-11-26-senaryo-semasi-design.md
"""

import json
import re
import sys
from pathlib import Path

# Karakter kimlikleri; referans görseli karakterler/<kimlik>.png
KARAKTERLER = ("sen", "nadide", "riza", "kerem", "murat", "ayla")
ANLATICI = "anlatici"
# Mekân kimlikleri; tarifleri hikaye.md'deki "Mekânlar" ve "Renk paleti" bölümlerinde.
MEKANLAR = ("otobus", "tesis", "istasyon", "dis")

SAHNE_EN_AZ, SAHNE_EN_COK = 8, 12
SURE_EN_AZ, SURE_EN_COK = 45, 90  # saniye
KELIME_SANIYEDE = 2.5  # tahmini konuşma hızı
SEN_CUMLE_SINIRI = 3
CUMLE_KELIME_SINIRI = 25
SON_BOLUM = 8  # finalde seçenek yok, yalnızca soru

KOK_ALANLAR = {"bolum", "baslik", "sahneler", "ikilem"}
SAHNE_ALANLARI = {"no", "gorsel", "karakterler", "cumleler"}
SAHNE_ISTEGE_BAGLI = {"mekan", "saat"}  # 'mekan' yoksa uyarı verilir; 'saat' isteğe bağlı
SAAT_ALANLARI = {"bas", "bit", "yon", "cumle", "kelime"}  # sahnedeki saat animasyonu
SAAT_ISTEGE_BAGLI = {"es"}
SAAT_YONLERI = ("geri", "ileri")
SAAT_ES_EN_COK = 5  # sahne başına eklenebilecek sessizlik (sn)
CUMLE_ALANLARI = {"konusan", "metin"}
IKILEM_ALANLARI = {"soru", "secenekler"}
SECENEK_ALANLARI = {"metin", "gorsel"}  # seçenek nesne yazılırsa; 'gorsel' isteğe bağlı


class SenaryoHatasi(Exception):
    """Senaryo okunamadı veya geçersiz. `hatalar` tüm sorunların listesidir."""

    def __init__(self, hatalar):
        self.hatalar = list(hatalar)
        super().__init__("\n".join(self.hatalar))


class _Denetci:
    """Hataları konumlarıyla birlikte toplar."""

    def __init__(self):
        self.hatalar = []
        self.uyarilar = []

    def hata(self, konum, mesaj):
        self.hatalar.append(f"{konum}: {mesaj}" if konum else mesaj)

    def uyari(self, konum, mesaj):
        self.uyarilar.append(f"{konum}: {mesaj}" if konum else mesaj)

    def nesne(self, deger, konum, zorunlu, izinli=None):
        """Değer bir sözlük mü, zorunlu alanlar var mı, fazladan alan var mı?"""
        if not isinstance(deger, dict):
            self.hata(konum, f"bir nesne ({{...}}) olmalı, {_tur_adi(deger)} bulundu.")
            return False
        for alan in sorted(zorunlu - deger.keys()):
            self.hata(konum, f"'{alan}' alanı eksik.")
        izinli = zorunlu if izinli is None else izinli
        for alan in sorted(deger.keys() - izinli):
            self.hata(konum, f"bilinmeyen alan '{alan}' (yazım hatası olabilir). "
                             f"Geçerli alanlar: {', '.join(sorted(izinli))}.")
        return True

    def metin(self, deger, konum):
        """Boş olmayan bir yazı mı?"""
        if not isinstance(deger, str):
            self.hata(konum, f"yazı (\"...\") olmalı, {_tur_adi(deger)} bulundu.")
            return False
        if not deger.strip():
            self.hata(konum, "boş olamaz.")
            return False
        return True

    def liste(self, deger, konum):
        if not isinstance(deger, list):
            self.hata(konum, f"liste ([...]) olmalı, {_tur_adi(deger)} bulundu.")
            return False
        return True


def _tur_adi(deger):
    if isinstance(deger, bool):
        return "true/false"
    return {dict: "nesne", list: "liste", str: "yazı", int: "sayı",
            float: "ondalık sayı", type(None): "null"}.get(type(deger), type(deger).__name__)


def _kelime_sayisi(metin):
    return len(metin.split())


def dogrula(veri, klasor_adi=None):
    """Senaryo verisini doğrular. (hatalar, uyarilar) döndürür; ikisi de Türkçe mesaj listesi.

    klasor_adi verilirse ("bolum_03" gibi) bölüm numarasıyla eşleştiği kontrol edilir.
    """
    d = _Denetci()
    if not d.nesne(veri, "", KOK_ALANLAR):
        return d.hatalar, d.uyarilar

    bolum = _bolum_dogrula(d, veri.get("bolum"), klasor_adi) if "bolum" in veri else None
    if "baslik" in veri:
        d.metin(veri["baslik"], "baslik")

    sen_sayisi = 0
    toplam_kelime = 0
    if "sahneler" in veri and d.liste(veri["sahneler"], "sahneler"):
        sahneler = veri["sahneler"]
        if not SAHNE_EN_AZ <= len(sahneler) <= SAHNE_EN_COK:
            d.hata("sahneler", f"{SAHNE_EN_AZ} ile {SAHNE_EN_COK} arasında sahne olmalı, "
                               f"{len(sahneler)} sahne var.")
        for i, sahne in enumerate(sahneler):
            sen, kelime = _sahne_dogrula(d, sahne, i)
            sen_sayisi += sen
            toplam_kelime += kelime

    if "ikilem" in veri:
        _ikilem_dogrula(d, veri["ikilem"], bolum)

    # Uyarılar yalnızca yapı sağlamsa anlamlı.
    if not d.hatalar:
        sure = toplam_kelime / KELIME_SANIYEDE
        if not SURE_EN_AZ <= sure <= SURE_EN_COK:
            d.uyari("", f"tahmini süre {sure:.0f} sn ({toplam_kelime} kelime); "
                        f"hedef {SURE_EN_AZ}–{SURE_EN_COK} sn.")
        if sen_sayisi > SEN_CUMLE_SINIRI:
            d.uyari("", f"'sen' {sen_sayisi} cümle konuşuyor; ana karakter seyrek konuşmalı "
                        f"(en fazla {SEN_CUMLE_SINIRI} önerilir).")
    return d.hatalar, d.uyarilar


def _bolum_dogrula(d, bolum, klasor_adi):
    if not isinstance(bolum, int) or isinstance(bolum, bool):
        d.hata("bolum", f"tam sayı olmalı, {_tur_adi(bolum)} bulundu.")
        return None
    if not 1 <= bolum <= SON_BOLUM:
        d.hata("bolum", f"1 ile {SON_BOLUM} arasında olmalı, {bolum} yazılmış.")
        return None
    if klasor_adi:
        eslesme = re.fullmatch(r"bolum_(\d+)", klasor_adi)
        if eslesme and int(eslesme.group(1)) != bolum:
            d.hata("bolum", f"dosya '{klasor_adi}' klasöründe ama bolum = {bolum}.")
    return bolum


def _sahne_dogrula(d, sahne, i):
    """Bir sahneyi doğrular; ('sen' cümle sayısı, kelime sayısı) döndürür."""
    konum = f"sahne {i + 1}"
    if not d.nesne(sahne, konum, SAHNE_ALANLARI, SAHNE_ALANLARI | SAHNE_ISTEGE_BAGLI):
        return 0, 0

    if "mekan" not in sahne:
        d.uyari(konum, f"'mekan' yazılmamış ({', '.join(MEKANLAR)}); görsel prompt'una "
                       "mekân tarifi eklenmeyecek.")
    elif not isinstance(sahne["mekan"], str):
        d.hata(f"{konum}, mekan", f"yazı olmalı, {_tur_adi(sahne['mekan'])} bulundu.")
    elif sahne["mekan"] not in MEKANLAR:
        d.hata(f"{konum}, mekan", f"bilinmeyen mekân '{sahne['mekan']}'. "
                                 f"Geçerli: {', '.join(MEKANLAR)}.")

    if "no" in sahne:
        no = sahne["no"]
        if not isinstance(no, int) or isinstance(no, bool):
            d.hata(f"{konum}, no", f"tam sayı olmalı, {_tur_adi(no)} bulundu.")
        elif no != i + 1:
            d.hata(f"{konum}, no", f"sahneler 1'den başlayıp sırayla numaralanmalı; "
                                  f"burada {i + 1} bekleniyordu, {no} yazılmış.")

    if "gorsel" in sahne:
        d.metin(sahne["gorsel"], f"{konum}, gorsel")

    sahnedekiler = set()
    if "karakterler" in sahne and d.liste(sahne["karakterler"], f"{konum}, karakterler"):
        for j, kimlik in enumerate(sahne["karakterler"]):
            k_konum = f"{konum}, karakter {j + 1}"
            if not isinstance(kimlik, str):
                d.hata(k_konum, f"yazı olmalı, {_tur_adi(kimlik)} bulundu.")
            elif kimlik not in KARAKTERLER:
                d.hata(k_konum, f"bilinmeyen karakter '{kimlik}'. "
                                f"Geçerli karakterler: {', '.join(KARAKTERLER)}.")
            elif kimlik in sahnedekiler:
                d.hata(k_konum, f"'{kimlik}' listede birden fazla kez geçiyor.")
            else:
                sahnedekiler.add(kimlik)

    sen, kelime = 0, 0
    if "saat" in sahne:
        _saat_dogrula(d, sahne["saat"], sahne.get("cumleler"), f"{konum}, saat")
    if "cumleler" in sahne and d.liste(sahne["cumleler"], f"{konum}, cumleler"):
        if not sahne["cumleler"]:
            d.hata(f"{konum}, cumleler", "en az bir cümle olmalı.")
        for j, cumle in enumerate(sahne["cumleler"]):
            c_konum = f"{konum}, cümle {j + 1}"
            if not d.nesne(cumle, c_konum, CUMLE_ALANLARI):
                continue
            if "konusan" in cumle:
                konusan = cumle["konusan"]
                if not isinstance(konusan, str):
                    d.hata(f"{c_konum}, konusan", f"yazı olmalı, {_tur_adi(konusan)} bulundu.")
                elif konusan != ANLATICI and konusan not in KARAKTERLER:
                    d.hata(f"{c_konum}, konusan",
                           f"bilinmeyen konuşan '{konusan}'. Geçerli: {ANLATICI}, "
                           f"{', '.join(KARAKTERLER)}.")
                elif konusan != ANLATICI and konusan not in sahnedekiler:
                    d.hata(f"{c_konum}, konusan",
                           f"'{konusan}' konuşuyor ama bu sahnenin 'karakterler' listesinde yok.")
                elif konusan == "sen":
                    sen += 1
            if "metin" in cumle and d.metin(cumle["metin"], f"{c_konum}, metin"):
                n = _kelime_sayisi(cumle["metin"])
                kelime += n
                if n > CUMLE_KELIME_SINIRI:
                    d.uyari(f"{c_konum}, metin", f"cümle {n} kelime; altyazıya sığması için "
                                                f"en fazla {CUMLE_KELIME_SINIRI} önerilir.")
    return sen, kelime


def kelime_kok(kelime):
    """Kelime karşılaştırması için: baştaki/sondaki noktalama atılır, Türkçe küçük harf."""
    kelime = kelime.strip(".,;:!?…\"'«»“”‘’()-")
    return kelime.replace("İ", "i").replace("I", "ı").lower()


def _saat_dakika(metin):
    """'SS:DD' → gece yarısından itibaren dakika; biçim yanlışsa None."""
    if not isinstance(metin, str):
        return None
    eslesme = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", metin)
    return int(eslesme.group(1)) * 60 + int(eslesme.group(2)) if eslesme else None


def _saat_dogrula(d, saat, cumleler, konum):
    if not d.nesne(saat, konum, SAAT_ALANLARI, SAAT_ALANLARI | SAAT_ISTEGE_BAGLI):
        return
    dakikalar = []
    for alan in ("bas", "bit"):
        if alan in saat:
            dk = _saat_dakika(saat[alan])
            if dk is None:
                d.hata(f"{konum}, {alan}", f"SS:DD biçiminde saat olmalı (ör. \"23:30\"), "
                                           f"{saat[alan]!r} yazılmış.")
            dakikalar.append(dk)
    if len(dakikalar) == 2 and None not in dakikalar and dakikalar[0] == dakikalar[1]:
        d.hata(konum, "başlangıç ve bitiş saati aynı; saat dönmez.")
    if "yon" in saat and saat["yon"] not in SAAT_YONLERI:
        d.hata(f"{konum}, yon", f"{', '.join(SAAT_YONLERI)} olmalı, {saat['yon']!r} yazılmış.")
    if "es" in saat:
        es = saat["es"]
        if (not isinstance(es, (int, float)) or isinstance(es, bool)
                or not 0 <= es <= SAAT_ES_EN_COK):
            d.hata(f"{konum}, es", f"0 ile {SAAT_ES_EN_COK} arasında saniye olmalı, "
                                   f"{es!r} yazılmış.")
    if "cumle" not in saat or not isinstance(cumleler, list):
        return
    no = saat["cumle"]
    if not isinstance(no, int) or isinstance(no, bool) or not 1 <= no <= len(cumleler):
        d.hata(f"{konum}, cumle", f"sahnedeki bir cümlenin sırası olmalı (1–{len(cumleler)}), "
                                  f"{no!r} yazılmış.")
        return
    cumle = cumleler[no - 1]
    if not isinstance(saat.get("kelime"), str) or not isinstance(cumle, dict)             or not isinstance(cumle.get("metin"), str):
        if "kelime" in saat and not isinstance(saat["kelime"], str):
            d.hata(f"{konum}, kelime", "yazı olmalı.")
        return
    aranan = kelime_kok(saat["kelime"])
    if not aranan or aranan not in [kelime_kok(k) for k in cumle["metin"].split()]:
        d.hata(f"{konum}, kelime", f"'{saat['kelime']}' kelimesi {no}. cümlede yok "
                                   f"(\"{cumle['metin']}\").")


def _ikilem_dogrula(d, ikilem, bolum):
    if not d.nesne(ikilem, "ikilem", {"soru"}, IKILEM_ALANLARI):
        return
    if "soru" in ikilem:
        d.metin(ikilem["soru"], "ikilem.soru")

    if bolum == SON_BOLUM:
        if "secenekler" in ikilem:
            d.hata("ikilem.secenekler", f"Bölüm {SON_BOLUM} finaldir; seçenek olmaz, "
                                        "yalnızca 'soru' yazılır.")
        return
    if "secenekler" not in ikilem:
        d.hata("ikilem", "'secenekler' alanı eksik (A ve B seçenekleri gerekli).")
        return
    secenekler = ikilem["secenekler"]
    if not d.nesne(secenekler, "ikilem.secenekler", {"A", "B"}):
        return
    for harf in ("A", "B"):
        if harf not in secenekler:
            continue
        deger, konum = secenekler[harf], f"ikilem.secenekler.{harf}"
        if isinstance(deger, dict):
            if d.nesne(deger, konum, {"metin"}, SECENEK_ALANLARI):
                if "metin" in deger:
                    d.metin(deger["metin"], f"{konum}.metin")
                if "gorsel" in deger:
                    d.metin(deger["gorsel"], f"{konum}.gorsel")
        elif not isinstance(deger, str):
            d.hata(konum, f"yazı (\"...\") ya da {{\"metin\", \"gorsel\"}} nesnesi olmalı, "
                          f"{_tur_adi(deger)} bulundu.")
        else:
            d.metin(deger, konum)


def secenek_metni(deger):
    """Seçenek değeri (yazı ya da {"metin", "gorsel"}) → ekranda yazacak metin."""
    return deger["metin"] if isinstance(deger, dict) else deger


def secenek_gorseli(deger):
    """Seçenek değerindeki görsel tarifi; yoksa None."""
    return deger.get("gorsel") if isinstance(deger, dict) else None


def senaryo_yukle(yol):
    """Dosyayı okur ve doğrular. Geçerliyse veriyi döndürür, değilse SenaryoHatasi fırlatır.

    Uyarılar fırlatılmaz; görmek için dogrula() kullanılır.
    """
    yol = Path(yol)
    if not yol.exists():
        raise SenaryoHatasi([f"Dosya bulunamadı: {yol}"])
    if yol.is_dir():
        raise SenaryoHatasi([f"Bu bir klasör, senaryo dosyası değil: {yol} "
                             f"(örnek: {yol / 'senaryo.json'})"])
    try:
        metin = yol.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise SenaryoHatasi([f"Dosya UTF-8 değil: {yol}. Editörde UTF-8 olarak kaydet."])
    except OSError as e:
        raise SenaryoHatasi([f"Dosya okunamadı: {yol} ({e.strerror or e}). "
                             "Başka bir program açık tutuyor olabilir."])
    try:
        veri = json.loads(metin)
    except json.JSONDecodeError as e:
        raise SenaryoHatasi([f"JSON okunamadı (satır {e.lineno}, sütun {e.colno}): {_json_hatasi(e)}"])
    except (ValueError, RecursionError):
        # Ör. binlerce basamaklı sayı veya aşırı iç içe parantez.
        raise SenaryoHatasi(["JSON okunamadı: dosyada aşırı büyük bir sayı veya "
                             "çok derin iç içe yapı var."])

    hatalar, _ = dogrula(veri, yol.parent.name)
    if hatalar:
        raise SenaryoHatasi(hatalar)
    return veri


def _json_hatasi(e):
    """json modülünün İngilizce mesajlarının sık görülenlerini Türkçeleştirir."""
    ceviri = {
        "Expecting ',' delimiter": "virgül eksik (bir önceki satırın sonuna bak).",
        "Expecting ':' delimiter": "iki nokta (:) eksik.",
        "Expecting property name enclosed in double quotes":
            "alan adı çift tırnakla yazılmalı; ya da son elemandan sonra fazladan virgül var.",
        "Expecting value": "değer bekleniyordu (fazladan virgül veya boş alan olabilir).",
        "Unterminated string starting at": "tırnak kapatılmamış.",
        "Extra data": "JSON bittikten sonra fazladan yazı var.",
        "Invalid control character at": "yazının içinde satır sonu var; \\n kullan.",
    }
    return ceviri.get(e.msg, e.msg)


def main(argv):
    if len(argv) != 1:
        print("Kullanım: python kod/senaryo.py bolumler/bolum_NN/senaryo.json")
        return 1
    yol = Path(argv[0])
    try:
        veri = senaryo_yukle(yol)
    except SenaryoHatasi as e:
        print(f"✗ {yol} geçersiz ({len(e.hatalar)} hata):")
        for h in e.hatalar:
            print(f"  - {h}")
        return 1

    _, uyarilar = dogrula(veri, yol.parent.name)
    cumleler = [c for s in veri["sahneler"] for c in s["cumleler"]]
    kelime = sum(_kelime_sayisi(c["metin"]) for c in cumleler)
    konusanlar = sorted({c["konusan"] for c in cumleler})
    print(f"✓ {yol} geçerli.")
    print(f"  Bölüm {veri['bolum']}: {veri['baslik']}")
    print(f"  {len(veri['sahneler'])} sahne, {len(cumleler)} cümle, "
          f"tahmini {kelime / KELIME_SANIYEDE:.0f} sn")
    print(f"  Konuşanlar: {', '.join(konusanlar)}")
    if uyarilar:
        print(f"  {len(uyarilar)} uyarı:")
        for u in uyarilar:
            print(f"  ! {u}")
    return 0


if __name__ == "__main__":
    # Windows konsolunda Türkçe karakterler ve ✓ işareti bozulmasın.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
