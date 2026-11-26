"""Kapak adımı: bölümün Reels kapak görselini (1080×1920) üretir.

Kapakta seri adı, "BÖLÜM N / 8", bölüm başlığı ve (Bölüm 2'den itibaren) önceki
bölümde kazanan seçim yazar; izleyici profil ızgarasında hangi bölüm olduğunu ve
hikâyenin hangi daldan ilerlediğini kapaktan anlar.
Yazılar Instagram profil ızgarasının gösterdiği orta 3:4 alanın (y 240–1680)
içinde kalır. Arka plan, bölümün bir sahne görselidir (varsayılan: sahne 1, varyant a).

Önceki seçim durum.json'dan okunur: {"bolumler": {"1": {"kazanan": "A", ...}}}.
Seçenek metni önceki bölümün senaryo.json'undaki ikilemden gelir.

Kullanım:
    python kod/kapak.py bolumler/bolum_01/senaryo.json                # → kapak.png
    python kod/kapak.py bolumler/bolum_02/senaryo.json --gorsel 4=b   # sahne 4, varyant b
    python kod/kapak.py bolumler/bolum_02/senaryo.json --onceki A     # durum.json yerine elle
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import SON_BOLUM, SenaryoHatasi, secenek_metni, senaryo_yukle  # noqa: E402
from montaj import FONT_ADI, FONT_DOSYASI, FONT_KLASORU, GEN, YUK, VURGU, BEYAZ  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
GUVENLI_UST, GUVENLI_ALT = 240, 1680  # profil ızgarası (3:4) bu aralığı gösterir


class KapakHatasi(Exception):
    pass


def tr_buyuk(metin):
    """Türkçe büyük harf: i → İ, ı → I."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def seri_adi(hikaye_metni):
    for satir in hikaye_metni.splitlines():
        if satir.startswith("# "):
            return satir[2:].strip()
    raise KapakHatasi("hikaye.md'de '# Seri Adı' başlığı yok.")


def onceki_secim(durum, bolum):
    """durum.json'dan önceki bölümün kazanan harfi (yoksa None)."""
    kayit = (durum or {}).get("bolumler", {}).get(str(bolum - 1), {})
    return kayit.get("kazanan")


def _ass_metin(m):
    return m.replace("\\", "").replace("{", "(").replace("}", ")")


def ass_metni(seri, bolum, baslik, secim=None):
    """secim: (harf, metin) ya da None."""
    stil = ("Style: {ad},{font},{boy},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
            "0,0,0,0,100,100,{aralik},0,1,{kontur},{golge},5,0,0,0,1")
    stiller = [
        stil.format(ad="Seri", font=FONT_ADI, boy=64, aralik=14, kontur=4, golge=2),
        stil.format(ad="Bolum", font=FONT_ADI, boy=150, aralik=2, kontur=8, golge=4),
        stil.format(ad="Baslik", font=FONT_ADI, boy=96, aralik=2, kontur=7, golge=3),
        stil.format(ad="Not", font=FONT_ADI, boy=46, aralik=0, kontur=4, golge=2),
        stil.format(ad="Golge", font=FONT_ADI, boy=10, aralik=0, kontur=0, golge=0),
    ]

    def olay(stil_adi, metin, katman=1):
        return f"Dialogue: {katman},0:00:00.00,0:00:01.00,{stil_adi},,0,0,0,,{metin}"

    # Yazıların okunması için üstte ve altta yumuşak kenarlı koyu bantlar
    bant = "{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H000000&\\1a&H{a}&\\blur{b}\\p1}}m 0 {y1} l {g} {y1} {g} {y2} 0 {y2}{{\\p0}}"
    olaylar = [
        olay("Golge", bant.format(a="50", b=90, y1=-200, y2=620, g=GEN), 0),
        olay("Golge", bant.format(a="40", b=110, y1=1260, y2=YUK + 200, g=GEN), 0),
        olay("Seri", f"{{\\pos(540,330)\\c{VURGU}}}{_ass_metin(tr_buyuk(seri))}"),
        olay("Bolum", f"{{\\pos(540,470)}}BÖLÜM {bolum}"
                      f"{{\\fs80\\c{VURGU}}} / {SON_BOLUM}"),
        olay("Baslik", f"{{\\pos(540,1470)}}{_ass_metin(tr_buyuk(baslik))}"),
    ]
    if secim:
        harf, metin = secim
        olaylar.append(olay("Not", f"{{\\pos(540,1590)}}Seçilen yol: "
                                   f"{{\\c{VURGU}}}{harf}{{\\c{BEYAZ}}} · {_ass_metin(metin)}"))
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {GEN}", f"PlayResY: {YUK}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *stiller, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *olaylar, ""])


def gorsel_sec(deger):
    """'4=b' → (4, 'b'); None → (1, 'a')."""
    if not deger:
        return 1, "a"
    m = re.fullmatch(r"(\d+)=([abc])", deger.strip())
    if not m:
        raise KapakHatasi(f"--gorsel '{deger}' anlaşılamadı; örnek: 4=b")
    return int(m.group(1)), m.group(2)


def _program(ad):
    yol = shutil.which(ad)
    if not yol:
        raise KapakHatasi(f"{ad} bulunamadı. Kurulum: KULLANIM.md.")
    return yol


def kapak_uret(arka_plan, ass, cikti):
    with tempfile.TemporaryDirectory() as tmp:
        is_ = Path(tmp)
        (is_ / "kapak.ass").write_text(ass, encoding="utf-8")
        (is_ / "fontlar").mkdir()
        shutil.copy2(FONT_KLASORU / FONT_DOSYASI, is_ / "fontlar" / FONT_DOSYASI)
        komut = [_program("ffmpeg"), "-v", "error", "-y", "-i", str(arka_plan),
                 "-vf", f"scale={GEN}:{YUK}:force_original_aspect_ratio=increase,"
                        f"crop={GEN}:{YUK},ass=kapak.ass:fontsdir=fontlar",
                 "-frames:v", "1", str(Path(cikti).resolve())]
        sonuc = subprocess.run(komut, cwd=is_, capture_output=True, encoding="utf-8",
                               errors="replace")
        if sonuc.returncode != 0:
            raise KapakHatasi("ffmpeg başarısız:\n" + sonuc.stderr.strip()[-600:])


def main(argv=None):
    p = argparse.ArgumentParser(description="Bölümün Reels kapağını üretir (kapak.png).")
    p.add_argument("senaryo", type=Path)
    p.add_argument("--gorsel", help="arka plan: sahne=varyant, ör. 4=b (varsayılan 1=a)")
    p.add_argument("--onceki", choices=["A", "B"], help="önceki bölümde kazanan (durum.json yerine)")
    a = p.parse_args(argv)
    try:
        veri = senaryo_yukle(a.senaryo)
        klasor = a.senaryo.resolve().parent
        bolum = veri["bolum"]
        seri = seri_adi((KOK / "hikaye.md").read_text(encoding="utf-8"))

        secim = None
        if bolum > 1:
            harf = a.onceki
            if not harf:
                durum_yolu = KOK / "durum.json"
                durum = (json.loads(durum_yolu.read_text(encoding="utf-8"))
                         if durum_yolu.exists() else None)
                harf = onceki_secim(durum, bolum)
            if not harf:
                raise KapakHatasi(f"Bölüm {bolum - 1}'in kazananı durum.json'da yok; "
                                  "--onceki A/B ver.")
            onceki = senaryo_yukle(klasor.parent / f"bolum_{bolum - 1:02d}" / "senaryo.json")
            secim = (harf, secenek_metni(onceki["ikilem"]["secenekler"][harf]))

        no, varyant = gorsel_sec(a.gorsel)
        arka = klasor / "gorseller" / f"sahne{no}_{varyant}.png"
        if not arka.exists():
            raise KapakHatasi(f"Arka plan görseli yok: {arka}")
        cikti = klasor / "kapak.png"
        kapak_uret(arka, ass_metni(seri, bolum, veri["baslik"], secim), cikti)
        print(f"Kapak hazır: {cikti}")
    except (KapakHatasi, SenaryoHatasi) as h:
        print(f"Hata: {h}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
