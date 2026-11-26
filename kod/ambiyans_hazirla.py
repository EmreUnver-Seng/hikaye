"""Ambiyans kaydını döngüye hazırlar: varliklar/ambiyans/<mekan>.mp3

Kaynaktan bir kesit alınır, sonu başına çapraz geçişle eklenir (döngü noktası duyulmaz)
ve ses düzeyi -24 LUFS'a ayarlanır. Montaj (montaj.py) bu dosyayı sahnenin 'mekan'ına
göre döngüyle ve kısık çalar.

Kullanım:
    python kod/ambiyans_hazirla.py kaynak.mp3 otobus --bas 350 --sure 100

Kaynaklar ve lisanslar: varliklar/ambiyans/KAYNAKLAR.md
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from senaryo import MEKANLAR  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
KLASOR = KOK / "varliklar" / "ambiyans"
GECIS = 4.0         # döngü noktasındaki çapraz geçiş (sn)
HEDEF_LUFS = -24


def hazirla_komutu(ffmpeg, kaynak, hedef, bas, sure):
    """Kaynağın [bas, bas+sure+GECIS] kesitinden kesintisiz döngü (süre = sure) üretir."""
    filtre = (f"[0:a]atrim=start={bas}:duration={sure + GECIS},asetpts=PTS-STARTPTS,"
              f"aresample=44100,aformat=channel_layouts=stereo,asplit[x][y];"
              f"[x]atrim=start={GECIS},asetpts=PTS-STARTPTS[govde];"
              f"[y]atrim=end={GECIS},asetpts=PTS-STARTPTS[bas];"
              f"[govde][bas]acrossfade=d={GECIS}:c1=tri:c2=tri,"
              f"loudnorm=I={HEDEF_LUFS}:TP=-2:LRA=7,aresample=44100[c]")
    return [ffmpeg, "-v", "error", "-y", "-i", str(kaynak), "-filter_complex", filtre,
            "-map", "[c]", "-c:a", "libmp3lame", "-b:a", "160k", str(hedef)]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    ayr = argparse.ArgumentParser(description="Ambiyans kaydını döngüye hazırlar.")
    ayr.add_argument("kaynak")
    ayr.add_argument("mekan", choices=MEKANLAR)
    ayr.add_argument("--bas", type=float, default=0.0, help="kesit başlangıcı (sn)")
    ayr.add_argument("--sure", type=float, default=100.0, help="döngü uzunluğu (sn)")
    args = ayr.parse_args(argv)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg bulunamadı. Kurulum: KULLANIM.md")
        return 1
    KLASOR.mkdir(parents=True, exist_ok=True)
    hedef = KLASOR / f"{args.mekan}.mp3"
    sonuc = subprocess.run(hazirla_komutu(ffmpeg, args.kaynak, hedef, args.bas, args.sure),
                           capture_output=True, encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        print("ffmpeg başarısız:\n" + "\n".join(sonuc.stderr.strip().splitlines()[-5:]))
        return 1
    print(f"✓ {hedef.relative_to(KOK).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
