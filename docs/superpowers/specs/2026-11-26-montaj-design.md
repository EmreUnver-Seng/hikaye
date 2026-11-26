# Montaj adımı: `montaj.py` (Yol haritası adım 4)

## Amaç
Bir bölümün görsellerini, cümle seslerini ve kelime zamanlamalarını ffmpeg ile dikey (1080×1920, 30 fps) tek bir videoda birleştirmek: sahne başına yavaş zoom, kelime vurgulu altyazı, sonda ikilem/seçenek kartı. Hedef platform TikTok/Instagram; öncelik tempo ve izlenme süresi (`hikaye.md` → Ton).

## Kararlar (kullanıcıyla)
- **Altyazı:** 2–4 kelimelik gruplar; o an söylenen kelime **hardal sarısı**, diğerleri beyaz. Kalın font, siyah kontur + hafif gölge, ekranın alt-orta kısmı.
- **Seçenek kartı:** Son sahnenin görseli karartılır; üstte ikilem sorusu, altında A ve B kutuları, en altta "Yorumlara A ya da B yaz".
- **Eksik sahne:** Tam montajda bir sahnenin görseli veya sesi eksikse tüm eksikler listelenir ve durulur. `--sahne 3` / `--sahne 1-3` ile yalnızca o sahnelerden önizleme çıkar (kart yine sonda).
- **Müzik/ambiyans yok (bu adımda).** Kullanıcı müzik değil, sahneye uygun ambiyans (ör. otobüs retarder sesi) düşünüyor; belki platformda kendisi ekler. **İlk tam bölüm çıktığında kullanıcıya hatırlatılacak**, kaynak (ElevenLabs ses efekti kredi harcar / ücretsiz kütüphaneler) o zaman konuşulacak.
- **Font:** Montserrat ExtraBold (`varliklar/fontlar/Montserrat-ExtraBold.ttf`, SIL OFL 1.1, `OFL.txt` yanında; kaynak: github.com/JulietaUla/Montserrat). Kullanıcı ileride değiştirebilir: font ayarı `montaj.py`'nin başında tek yerde (dosya adı + ASS'deki font adı).
- **Varyant:** Varsayılan `a`; `--varyant 3=b,5=c` ile sahne başına değiştirilir. Asıl seçim ekranı adım 5'in (`yeni_bolum.py`) işi; bu modül seçimi parametre olarak alır.

## Yaklaşımlar
- **Seçilen — önce plan, sonra parça parça render:** Python tüm zaman çizelgesini, ASS altyazı dosyasını ve ffmpeg komut listelerini hesaplar (hepsi ffmpeg'siz test edilir). ffmpeg önce her sahneyi zoom'lu ayrı klip olarak, sonra tek geçişte birleştirir (ses + altyazı + kart). Hata hangi sahnede belli olur.
- **Elenen — tek dev `filter_complex`:** Biraz hızlı ama 12 sahnede okunmaz, hata ayıklaması zor.
- **Elenen — MoviePy vb.:** Yeni bağımlılık, yavaş; altyazı vurgusu yine elle.

## Kullanım
```
python kod/montaj.py bolumler/bolum_01/senaryo.json                    # tam bölüm → video.mp4
python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 3          # önizleme → onizleme.mp4
python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 1-3 --varyant 1=b,3=c
python kod/montaj.py bolumler/bolum_01/senaryo.json --kuru             # render yok: plan ve süreler
```
Çıktı `bolumler/bolum_NN/video.mp4` (tam) veya `onizleme.mp4` (`--sahne`). İkisi de git dışında (`bolumler/*/*.mp4`). Önce geçici ada yazılır, başarılıysa yerine konur.

## Girdiler ve doğrulama
1. `senaryo_yukle(yol)` (geçersizse `senaryo.py` mesajları, çıkış 1).
2. **Senaryo sırayla gezilir**, `zamanlama.json` değil (senaryodan silinen cümlelerin eski mp3/kayıtları klasörde kalabiliyor). Kapsamdaki her sahne için:
   - Görsel: `gorseller/sahneN_<harf>.png` var mı.
   - Her cümle: `sesler/sSS_cC.mp3` ve `zamanlama.json`'da aynı anahtarlı kayıt var mı; kaydın `metin`i senaryodakiyle aynı mı (değilse "ses eski → `ses.py` çalıştır").
   - Tüm eksik/eski olanlar birlikte listelenir, çıkış 1. Mesaj, çalıştırılacak komutu söyler (`gorsel.py ... --yerlestir N`, `ses.py ... --sahne N`).
3. `--varyant` yalnızca var olan sahne numarası ve `a/b/c` alır; `--sahne` aralığı senaryoda olmalı.
4. Cümle süresi = **mp3'ün gerçek süresi** (ffprobe), kayıttaki `sure` değil (o son harfin bitişi; sondaki sessizliği saymaz).

## Zaman çizelgesi
- Video 0'da ilk sahneyle başlar (giriş yok: ilk 2–3 sn kanca).
- Sahne içinde cümleler arka arkaya; aralarında **0,15 sn** sessizlik. Sahnenin son cümlesinden sonra **0,35 sn** (sahne geçişi). Görsel sahne boyunca ekranda kalır; geçiş sert kesme.
- Sahne süresi = Σ(mp3 süreleri) + cümle araları + 0,35.
- Ardından **kart: 4 sn**, sessiz.
- Tam montajda toplam süre 45–90 sn dışındaysa uyarı (hata değil).
- Kare hesabı: her klip `round(süre × 30)` kare; sesin konumları aynı yuvarlanmış sahne başlangıçlarından hesaplanır (görüntü–ses kayması birikmesin).

## Görüntü
- Her sahne klibi: görsel 2160×3840'a büyütülür, `zoompan` ile 1080×1920'ye; tek sahneler yakınlaşır (zoom 1,00→1,08), çift sahneler uzaklaşır (1,08→1,00), merkezde. (Önce büyütmek zoom titremesini önler.)
- Kart klibi: kapsamdaki son sahnenin görseli sabit (zoom 1,04), %60 karartılmış.
- Kodlama: H.264 (`libx264`, `yuv420p`, CRF 20), ses AAC 192k, `+faststart`.

## Altyazı (ASS, `PlayResX/Y` 1080×1920)
- **Gruplama** (her cümle kendi içinde, cümleler arası grup birleşmez): en çok 4 kelime ve ~22 karakter; `.?!…` ile biten kelimeden sonra grup kapanır; virgülle biten kelimede grup en az 2 kelimeyse kapanır.
- **Zamanlama:** grup ilk kelimesinin başlangıcında görünür; bir sonraki grubun başlangıcına kadar (cümlenin son grubu: son kelime bitişi + 0,3 sn, ama bir sonraki cümle/sahne başlangıcını geçmez) kalır. Grup içinde her kelime için ayrı olay: o kelime sarı, gerisi beyaz; bir kelimenin vurgusu bir sonraki kelimenin başlangıcına kadar sürer.
- **Görünüm:** Montserrat ExtraBold 86 px, beyaz `&H00FFFFFF`, vurgu hardal `#E8B82D`, siyah kontur 7, gölge 3, alt-orta hizalı, alt boşluk 420 px (TikTok'un alt arayüzü yazıyı örtmesin), yan boşluk 80 px, otomatik satır kırma.
- Metindeki `{`, `}` ve `\` ASS'yi bozmasın diye kaçırılır/temizlenir. Noktalama kelimeye yapışık, aynen gösterilir.
- Konuşan ayrımı görsel olarak yapılmaz (ses zaten farklı).

## Seçenek kartı (ASS olayları, kart süresince)
- Soru: beyaz, 72 px, ekranın ~%35'inde, ortalı, satır kırmalı.
- A ve B: koyu yarı saydam kutu içinde (`BorderStyle 3`), harf hardal sarısı, seçenek metni beyaz, 64 px; A ~%52, B ~%62 yükseklikte; 0,25 sn gecikmeli, kısa belirme (`\fad`).
- Alt satır: "Yorumlara A ya da B yaz", 48 px, ~%75.
- Bölüm 8 (`secenekler` yok): yalnızca soru + "Yorumlara yaz".

## Ses
Tek `filter_complex`: her mp3 `aresample=44100`, sonuna slotuna kadar sessizlik (`apad=whole_dur`), kart için 4 sn sessizlik; hepsi `concat`. Toplam ses süresi = video süresi.

## Çapraz platform
`pathlib.Path`, `encoding="utf-8"`, `shutil.which("ffmpeg"/"ffprobe")`, komutlar liste, `shell=True` yok. Windows'ta `ass` filtresinde `C:` iki noktası sorun çıkardığı için ffmpeg geçici çalışma klasöründe (`cwd`) çalıştırılır ve ASS + font klasörü **göreli, `/` ayraçlı** yollarla verilir. Geçici klasör bölüm klasörünün içinde açılır (`tempfile.TemporaryDirectory(dir=...)`; aynı sürücü, göreli yol kurulabilir) ve iş bitince/hata olsa da silinir. Font proje içinden (`fontsdir`), sistem fontu kullanılmaz.

## Test: `kod/test_montaj.py` (düz Python, pytest yok)
ffmpeg'siz: `--sahne`/`--varyant` ayrıştırma ve hataları; eksik görsel/ses/kayıt ve eski metin listesi; zaman çizelgesi (süreler parametre olarak verilir, ffprobe çağrılmaz; kare yuvarlama); gruplama (noktalama, virgül, 4 kelime/karakter sınırı, tek kelimelik cümle); ASS zaman biçimi (`0:00:01.23`), kaçırma, vurgu olayları, kartta A/B ve bölüm 8; ffmpeg komut listeleri (liste, göreli yollar). ffmpeg varsa: geçici klasörde üretilmiş küçük görseller + kısa sessiz mp3'lerle uçtan uca render, çıktının süresi ffprobe ile kontrol (ffmpeg yoksa atlanır).
**Gerçek deneme:** Bölüm 1 sahne 3 (gerçek sesler + kullanıcının Gemini'de üreteceği görseller) → `--sahne 3`.

## Proje geneline etkiler
- `CLAUDE.md`: yol haritasında adım 4 işaretlenir (tasarım, kontrol ve test komutu); klasör yapısına `varliklar/fontlar/` eklenir.
- `KULLANIM.md` bölüm üretimi listesine montaj komutu (`--sahne` önizleme, `--varyant`).

## Bilinçli olarak yok
Müzik/ambiyans (yukarıda), sahne geçiş efektleri, açılış başlık kartı, konuşana göre altyazı rengi, AI etiketi (platformda eklenir).

## Uygulayıcıya bırakılanlar
İç fonksiyon adları, mesajların tam metni, kart öğelerinin piksel konumlarında küçük ayarlar (gerçek denemede göze göre).
