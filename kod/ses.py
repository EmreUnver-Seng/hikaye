"""Ses adımı: senaryodaki her cümleyi ElevenLabs ile seslendirir.

Her cümle, konuşanın karakterler/sesler.json'daki sabit sesiyle seslendirilir.
Altyazı için kelime zamanlamaları sesler/zamanlama.json'a yazılır.
Var olan ve değişmemiş cümleler atlanır; her harcamadan önce kota gösterilip onay istenir.

Kullanım:
    python kod/ses.py bolumler/bolum_01/senaryo.json              # eksik ve değişen cümleler
    python kod/ses.py bolumler/bolum_01/senaryo.json --sahne 3    # yalnızca 3. sahne
    python kod/ses.py bolumler/bolum_01/senaryo.json --cumle 3.2  # tek cümleyi yeniden üret
    python kod/ses.py bolumler/bolum_01/senaryo.json --kuru       # hiçbir şey üretmeden say

Tasarım: docs/superpowers/specs/2026-11-26-ses-design.md
"""

import argparse
import base64
import json
import os
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import ANLATICI, KARAKTERLER, SenaryoHatasi, senaryo_yukle  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
SES_HARITASI = KOK / "karakterler" / "sesler.json"
ZAMANLAMA = "zamanlama.json"
SES_BICIMI = "mp3_44100_128"
DIL = "tr"
DIL_KODU_DESTEKLEMEYEN = {"eleven_multilingual_v2"}
BILINEN_KONUSANLAR = (ANLATICI, *KARAKTERLER)

# kaynak: aynı metin/ses/modelle hazır başka bir kaydın anahtarı (cümle eklenip
# silinince numaralar kayar); varsa API yerine o ses kopyalanır, kredi harcanmaz.
Is = namedtuple("Is", "anahtar sahne cumle konusan metin ses_id uret kaynak",
                defaults=(None,))


class SesHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek hata (bir veya birden fazla satır)."""

    def __init__(self, hatalar):
        self.hatalar = [hatalar] if isinstance(hatalar, str) else list(hatalar)
        super().__init__("\n".join(self.hatalar))


# --- Ses eşlemesi ---

def ses_haritasi_dogrula(veri):
    """sesler.json içeriğini doğrular, {"model": str, "sesler": {kimlik: id}} döndürür."""
    if not isinstance(veri, dict):
        raise SesHatasi("sesler.json bir JSON nesnesi ({...}) olmalı.")
    hatalar = []
    model = veri.get("model")
    if not isinstance(model, str) or not model.strip():
        hatalar.append("sesler.json: 'model' alanı boş olmayan bir metin olmalı (ör. \"eleven_v4\").")
    sesler = veri.get("sesler")
    harita = {}
    if not isinstance(sesler, dict):
        hatalar.append("sesler.json: 'sesler' alanı {konusan: {\"id\": ...}} biçiminde olmalı.")
    else:
        for kimlik, deger in sesler.items():
            if kimlik not in BILINEN_KONUSANLAR:
                hatalar.append(f"sesler.json: bilinmeyen konuşan '{kimlik}' "
                               f"(bilinenler: {', '.join(BILINEN_KONUSANLAR)}).")
                continue
            ses_id = deger.get("id") if isinstance(deger, dict) else None
            if not isinstance(ses_id, str) or not ses_id.strip():
                hatalar.append(f"sesler.json: '{kimlik}' için 'id' boş olmayan bir metin olmalı.")
                continue
            harita[kimlik] = ses_id.strip()
    if hatalar:
        raise SesHatasi(hatalar)
    return {"model": model.strip(), "sesler": harita}


def ses_haritasi_yukle(yol):
    yol = Path(yol)
    if not yol.is_file():
        raise SesHatasi(f"Ses eşlemesi bulunamadı: {yol}")
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SesHatasi(f"{yol}: JSON okunamadı (satır {e.lineno}, sütun {e.colno}).") from e
    return ses_haritasi_dogrula(veri)


# --- Kelime zamanlaması ---

def _alan(nesne, ad):
    return nesne.get(ad) if isinstance(nesne, dict) else getattr(nesne, ad, None)


def _sozluk(hizalama):
    if isinstance(hizalama, dict):
        return hizalama
    if hasattr(hizalama, "model_dump"):
        return hizalama.model_dump()
    return dict(vars(hizalama))


def hizalama_sec(cevap):
    """API cevabından harf zamanlamalarını alır (önce alignment, yoksa normalized_alignment)."""
    for ad in ("alignment", "normalized_alignment"):
        hizalama = _alan(cevap, ad)
        if hizalama:
            hizalama = _sozluk(hizalama)
            if hizalama.get("characters"):
                return hizalama
    raise SesHatasi("ElevenLabs cevabında harf zamanlaması yok; altyazı için gerekli.")


def kelimeleri_cikar(hizalama):
    """Harf zamanlamalarından [{"kelime", "baslangic", "bitis"}] listesi çıkarır."""
    harfler = hizalama["characters"]
    baslar = hizalama["character_start_times_seconds"]
    bitisler = hizalama["character_end_times_seconds"]
    kelimeler, parca, bas, bit = [], [], None, None
    for harf, b, s in zip(harfler, baslar, bitisler):
        if harf.isspace():
            if parca:
                kelimeler.append({"kelime": "".join(parca), "baslangic": round(bas, 3),
                                  "bitis": round(bit, 3)})
            parca = []
            continue
        if not parca:
            bas = b
        parca.append(harf)
        bit = s
    if parca:
        kelimeler.append({"kelime": "".join(parca), "baslangic": round(bas, 3),
                          "bitis": round(bit, 3)})
    return kelimeler


# --- İş listesi ---

def dosya_adi(sahne, cumle):
    return f"s{sahne:02d}_c{cumle}"


def kayitlari_yukle(klasor):
    """zamanlama.json'daki cümle kayıtlarını döndürür (dosya yoksa boş)."""
    yol = Path(klasor) / ZAMANLAMA
    if not yol.exists():
        return {}
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SesHatasi(f"{yol} bozuk ({e}). Dosyayı sil veya düzelt; silersen "
                        "tüm cümleler yeniden üretilir.") from e
    if not isinstance(veri, dict) or not isinstance(veri.get("cumleler"), dict):
        raise SesHatasi(f"{yol} beklenen biçimde değil ('cumleler' yok). "
                        "Dosyayı sil veya düzelt; silersen tüm cümleler yeniden üretilir.")
    return veri["cumleler"]


def isleri_hazirla(veri, harita, kayitlar, klasor, sahne=None, cumle=None):
    """Kapsamdaki her cümle için Is döndürür; uret=False yalnızca hazır ve değişmemişse."""
    sahneler = {s["no"]: s for s in veri["sahneler"]}
    if cumle is not None:
        sahne_no, cumle_no = cumle
        if sahne_no not in sahneler:
            raise SesHatasi(f"Sahne {sahne_no} yok (senaryoda {len(sahneler)} sahne var).")
        adet = len(sahneler[sahne_no]["cumleler"])
        if not 1 <= cumle_no <= adet:
            raise SesHatasi(f"Sahne {sahne_no}'te {cumle_no}. cümle yok ({adet} cümle var).")
    elif sahne is not None and sahne not in sahneler:
        raise SesHatasi(f"Sahne {sahne} yok (senaryoda {len(sahneler)} sahne var).")

    def _hazir_mi(anahtar, metin, ses_id):
        k = kayitlar.get(anahtar) or {}
        return ((Path(klasor) / f"{anahtar}.mp3").exists() and k.get("metin") == metin
                and k.get("ses_id") == ses_id and k.get("model") == harita["model"])

    isler = []
    for s in veri["sahneler"]:
        if sahne is not None and s["no"] != sahne:
            continue
        if cumle is not None and s["no"] != cumle[0]:
            continue
        for i, c in enumerate(s["cumleler"], start=1):
            if cumle is not None and i != cumle[1]:
                continue
            anahtar = dosya_adi(s["no"], i)
            ses_id = harita["sesler"].get(c["konusan"])
            uret = cumle is not None or not _hazir_mi(anahtar, c["metin"], ses_id)
            kaynak = None
            if uret and cumle is None and ses_id is not None:
                kaynak = next((a for a in sorted(kayitlar) if a != anahtar
                               and _hazir_mi(a, c["metin"], ses_id)), None)
            isler.append(Is(anahtar, s["no"], i, c["konusan"], c["metin"], ses_id, uret, kaynak))
    return isler


def eksik_sesler(isler):
    return sorted({i.konusan for i in isler if i.ses_id is None})


def karakter_sayisi(isler):
    return sum(len(i.metin) for i in isler if i.uret and i.kaynak is None)


# --- ElevenLabs ---

def _api_hatasi(e):
    """ElevenLabs hatasını Türkçe SesHatasi'na çevirir."""
    durum = getattr(e, "status_code", None)
    govde = str(getattr(e, "body", "") or e)
    if "quota_exceeded" in govde:
        return SesHatasi("ElevenLabs kotası bitti. Bu ay için kalan karakter yetmiyor.")
    if "voice_not_found" in govde or durum == 404:
        return SesHatasi("ElevenLabs sesi bulamadı: karakterler/sesler.json'daki ID'yi kontrol et.")
    if durum == 401:
        return SesHatasi("ElevenLabs anahtarı geçersiz veya yetkisiz: .env içindeki "
                         "ELEVENLABS_API_KEY'i kontrol et.")
    if durum is None:
        return SesHatasi(f"ElevenLabs'e bağlanılamadı: {type(e).__name__}: {str(e)[:200]}")
    return SesHatasi(f"ElevenLabs hatası ({durum}): {govde[:200]}")


def kalan_kota(istemci):
    """(kalan, limit) karakter; istemci yoksa None."""
    if istemci is None:
        return None
    try:
        abonelik = istemci.user.subscription.get()
    except Exception as e:  # noqa: BLE001
        raise _api_hatasi(e) from e
    return abonelik.character_limit - abonelik.character_count, abonelik.character_limit


def _cumleyi_seslendir(istemci, is_, model):
    secenekler = {"text": is_.metin, "model_id": model, "output_format": SES_BICIMI}
    if model not in DIL_KODU_DESTEKLEMEYEN:
        secenekler["language_code"] = DIL
    try:
        cevap = istemci.text_to_speech.convert_with_timestamps(is_.ses_id, **secenekler)
    except Exception as e:  # noqa: BLE001
        raise _api_hatasi(e) from e
    return base64.b64decode(cevap.audio_base_64), hizalama_sec(cevap)


def _kaydet(klasor, bolum, kayitlar):
    yol = Path(klasor) / ZAMANLAMA
    gecici = yol.with_name(ZAMANLAMA + ".tmp")
    gecici.write_text(json.dumps({"bolum": bolum, "cumleler": kayitlar},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(yol)


def _kopyala(klasor, bolum, kayitlar, kopyalar, yaz):
    """Numarası kaymış cümlelerin hazır seslerini yeni adlarına kopyalar (API yok).

    Önce bütün kaynaklar belleğe okunur, sonra yazılır: zincirleme kaymada
    (c1→c2, c2→c3) bir kaynağın üzerine okunmadan yazılmasın diye.
    """
    if not kopyalar:
        return
    okunan = [(i, (klasor / f"{i.kaynak}.mp3").read_bytes(), dict(kayitlar[i.kaynak]))
              for i in kopyalar]
    for is_, ses, kayit in okunan:
        (klasor / f"{is_.anahtar}.mp3").write_bytes(ses)
        kayit.update(sahne=is_.sahne, cumle=is_.cumle, konusan=is_.konusan,
                     dosya=f"{is_.anahtar}.mp3")
        kayitlar[is_.anahtar] = kayit
        yaz(f"↻ {is_.anahtar} ← {is_.kaynak} (kredi harcanmadı)")
    _kaydet(klasor, bolum, kayitlar)


# --- Akış ---

def seslendir(veri, klasor, harita, istemci, sahne=None, cumle=None, kuru=False,
              sor=input, yaz=print):
    """Kapsamdaki cümleleri seslendirir. Çıkış kodu döndürür; API/dosya hatasında SesHatasi."""
    klasor = Path(klasor)
    kayitlar = kayitlari_yukle(klasor)
    isler = isleri_hazirla(veri, harita, kayitlar, klasor, sahne, cumle)

    eksik = eksik_sesler(isler)
    if eksik:
        yaz(f"✗ Şu konuşanların sesi yok: {', '.join(eksik)}")
        yaz("  karakterler/sesler.json'a ekle, ör.: \"riza\": {\"id\": \"<ses ID>\", \"ad\": \"<ad>\"}")
        yaz("  (Yeni karakter için önce kısa bir dinleme denemesiyle ses seç.) Hiçbir şey üretilmedi.")
        return 1

    if sahne is None and cumle is None:
        gecerli = {dosya_adi(s["no"], i) for s in veri["sahneler"]
                   for i in range(1, len(s["cumleler"]) + 1)}
        fazla = sorted(set(kayitlar) - gecerli)
        if fazla:
            yaz(f"! Senaryoda artık olmayan kayıtlar (silinmedi): {', '.join(fazla)}")

    uretilecek = [i for i in isler if i.uret]
    if not uretilecek:
        yaz(f"✓ Hepsi hazır ({len(isler)} cümle). Kredi harcanmadı.")
        return 0

    kopyalar = [i for i in uretilecek if i.kaynak]
    yeniler = [i for i in uretilecek if not i.kaynak]
    karakter = karakter_sayisi(isler)
    if kopyalar:
        yaz(f"{len(kopyalar)} cümlenin sesi hazır, yalnızca numarası kaymış: "
            "kredi harcamadan kopyalanacak.")
    if not yeniler:
        if kuru:
            yaz("(--kuru: hiçbir şey değiştirilmedi.)")
            return 0
        _kopyala(klasor, veri["bolum"], kayitlar, kopyalar, yaz)
        yaz("✓ Hepsi hazır. Kredi harcanmadı.")
        return 0
    yaz(f"{len(yeniler)} cümle üretilecek, {len(isler) - len(uretilecek)} atlanacak, "
        f"{karakter} karakter harcanacak (model: {harita['model']}).")
    kota = kalan_kota(istemci)
    if kota is None:
        if not kuru:
            raise SesHatasi(".env içinde ELEVENLABS_API_KEY yok; ses üretilemez.")
        yaz("Kalan kota: bilinmiyor (.env içinde ELEVENLABS_API_KEY yok).")
        return 0
    kalan, limit = kota
    yaz(f"Kalan kota: {kalan}/{limit} karakter.")
    if kuru:
        yaz("(--kuru: hiçbir şey üretilmedi.)")
        return 0
    if karakter > kalan:
        yaz(f"✗ Kota yetmiyor: {karakter} karakter gerekiyor, {kalan} kaldı. Hiçbir şey üretilmedi.")
        return 1
    try:
        cevap = sor("Devam edilsin mi? (e/h) ")
    except (EOFError, KeyboardInterrupt):
        cevap = "h"
    if (cevap or "").strip().lower() not in ("e", "evet"):
        yaz("Vazgeçildi, hiçbir şey üretilmedi.")
        return 0

    klasor.mkdir(parents=True, exist_ok=True)
    _kopyala(klasor, veri["bolum"], kayitlar, kopyalar, yaz)
    for is_ in yeniler:
        ses, hizalama = _cumleyi_seslendir(istemci, is_, harita["model"])
        (klasor / f"{is_.anahtar}.mp3").write_bytes(ses)
        bitisler = hizalama["character_end_times_seconds"]
        kayitlar[is_.anahtar] = {
            "sahne": is_.sahne, "cumle": is_.cumle, "konusan": is_.konusan,
            "metin": is_.metin, "ses_id": is_.ses_id, "model": harita["model"],
            "dosya": f"{is_.anahtar}.mp3", "sure": round(bitisler[-1], 3) if bitisler else 0.0,
            "kelimeler": kelimeleri_cikar(hizalama),
        }
        _kaydet(klasor, veri["bolum"], kayitlar)
        yaz(f"✓ {is_.anahtar} ({is_.konusan}, {kayitlar[is_.anahtar]['sure']:.1f} sn)")

    tum = isleri_hazirla(veri, harita, kayitlar, klasor)
    hazir = [i for i in tum if not i.uret]
    toplam = sum(kayitlar[i.anahtar]["sure"] for i in hazir)
    yaz(f"Bitti: {len(yeniler)} üretildi, {len(kopyalar)} kopyalandı, "
        f"{len(isler) - len(uretilecek)} atlandı. "
        f"Bölümde {len(hazir)}/{len(tum)} cümle hazır, toplam {toplam:.1f} sn.")
    return 0


def _cumle_numarasi(metin):
    parcalar = metin.split(".")
    if len(parcalar) != 2 or not all(p.isdigit() for p in parcalar):
        raise argparse.ArgumentTypeError(f"'{metin}' geçersiz; SAHNE.CÜMLE biçiminde yaz (ör. 3.2).")
    return int(parcalar[0]), int(parcalar[1])


def _istemci_olustur():
    from dotenv import load_dotenv
    load_dotenv(KOK / ".env")
    anahtar = os.getenv("ELEVENLABS_API_KEY")
    if not anahtar:
        return None
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key=anahtar)


def main(argv):
    ayristirici = argparse.ArgumentParser(
        prog="ses.py", description="Senaryodaki cümleleri ElevenLabs ile seslendirir.")
    ayristirici.add_argument("senaryo", type=Path, help="bolumler/bolum_NN/senaryo.json")
    kapsam = ayristirici.add_mutually_exclusive_group()
    kapsam.add_argument("--sahne", type=int, help="yalnızca bu sahne")
    kapsam.add_argument("--cumle", type=_cumle_numarasi,
                        help="tek cümleyi (var olsa da) yeniden üret, ör. 3.2")
    ayristirici.add_argument("--kuru", action="store_true",
                             help="hiçbir şey üretme: ne üretileceğini, karakter ve kotayı göster")
    args = ayristirici.parse_args(argv)

    try:
        veri = senaryo_yukle(args.senaryo)
    except SenaryoHatasi as e:
        print(f"✗ {args.senaryo} geçersiz ({len(e.hatalar)} hata):")
        for h in e.hatalar:
            print(f"  - {h}")
        return 1
    try:
        harita = ses_haritasi_yukle(SES_HARITASI)
        return seslendir(veri, args.senaryo.parent / "sesler", harita, _istemci_olustur(),
                         sahne=args.sahne, cumle=args.cumle, kuru=args.kuru)
    except SesHatasi as e:
        for h in e.hatalar:
            print(f"✗ {h}")
        return 1


if __name__ == "__main__":
    # Windows konsolunda Türkçe karakterler ve ✓ işareti bozulmasın.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")  # argparse hata mesajları
    sys.exit(main(sys.argv[1:]))
