# Proje: AI ile interaktif hikâye videoları

Instagram/TikTok için yapay zekâ çizimli, yapay zekâ seslendirmeli, seçmeli hikâye videoları üreten **yarı otomatik** bir Python pipeline'ı.
Her bölüm bir ikilemle biter; izleyici yorum veya anketle seçer, kazanan seçim bir sonraki bölümün girdisi olur.

İletişim dili: **Türkçe**. Geliştirici: 3. sınıf yazılım mühendisliği öğrencisi.
Platform: **macOS (Apple Silicon)** ana cihaz + **Windows** ikinci cihaz. Proje GitHub üzerinden iki cihazda sürdürülür.

### Çapraz platform kuralları (kod yazarken uy)
- Yollar her zaman `pathlib.Path` ile kurulur; elle `/` veya `\` birleştirilmez, sabit mutlak yol yazılmaz.
- Dosyalar her zaman `encoding="utf-8"` ile açılır (Windows varsayılanı UTF-8 değil).
- Dış programlar (`ffmpeg`) PATH'ten bulunur: `shutil.which("ffmpeg")`.
- Altyazı fontu sistem klasöründen değil, projedeki `varliklar/fontlar/` klasöründen yüklenir (Mac ve Windows font yolları farklı).
- `subprocess` çağrılarında komut liste olarak verilir, `shell=True` kullanılmaz.

### Token tasarrufu (Claude için)
- Bu projede **superpowers süreç becerilerini kullanma**: brainstorming, writing-plans, tasarım/spec belgesi yazma, bağımsız inceleme ajanları, subagent-driven-development, TDD. İsteneni doğrudan yap. Kullanıcı açıkça isterse kullanılabilir.
- Alt ajan başlatma; gereksiz dosya okuma. Küçük değişiklikte mevcut testleri çalıştırmak yeterli.
- Bir iş bitince yeni oturum **açma**; sıradaki adımı söyle, oturumu kullanıcı açar.

## Alınmış kararlar
- **Araçlar:** Claude (senaryo; **API kullanılmaz**, Claude Code üzerinden Pro aboneliğiyle), Gemini **uygulaması** (görsel; **API kullanılmaz**, ücretli olduğu için. Görseller uygulamada elle üretilir, kod prompt'u hazırlar ve dosyayı yerleştirir), ElevenLabs (seslendirme; istenirse efekt ve müzik).
- **Çalışma şekli:** Yarı otomatik. Kod tekrar eden işleri yapar (API çağrıları, dosya indirme ve adlandırma, montaj, altyazı, durum kaydı). Yaratıcı kararları kullanıcı verir.
- **Görsel stil:** Sahneler 2.5D. Karakterler aynı 2B çizim diliyle kalır: koyu kontur, iki tonlu gölge, orta detay, aynı yüzler ve kıyafetler. Derinlik mekân perspektifi, ön/orta/arka plan ayrımı ve sinematik ışıktan gelir. Sahne isteğine karakter referanslarından sonra `karakterler/stil-sahne.png` eklenir. Karakter sayfası ve seçim kartı `karakterler/stil.png` ile üretilir.
- **Format:** Dikey 9:16, bölüm başına 45–90 sn, 8–12 sahne, altyazılı.
- **Tür:** Gerilim/gizem. Hikâye: "Son Durak" (8 bölüm, gece otobüsü, "sen" diye hitap eden anlatıcı). Ayrıntı: `hikaye.md`.

## Bir bölümün akışı (kullanıcının gözünden)
1. Kullanıcı Claude Code'a "Bölüm N'in senaryosunu yaz" der. Claude `hikaye.md` ve `durum.json` dosyalarını okuyup `bolumler/bolum_NN/senaryo.json` dosyasını yazar. (İleride `senaryo.py` bunu `claude -p` ile otomatik yapabilir.) **Kontrol noktası:** Kullanıcı senaryoyu okuyup düzenler. **Kalıcı kural:** Bölüm 2'den itibaren her senaryo, önceki bölümde seçilmeyen yolu hatırlatan kısa bir sekansla **açılır** (1. sahne) (ayrıntı: `hikaye.md` → "Seçilmeyen yol sekansı"). **Hatırlatma (kural değil, 2026-11-28):** Senaryoya başlamadan önce kullanıcıya önceki bölümün oy sonucunu (yüzde ve oy sayısı, ör. "%62'niz B dedi, 140 oy") açılışa eklemek isteyip istemediğini sor; oy verisi henüz `durum.json`'da tutulmuyor, kullanıcıdan al.
2. `python kod/yeni_bolum.py` komutu çalıştırılır; mevcut `senaryo.json` dosyasını girdi olarak alır.
3. `gorsel.py` her sahne için istek (referans görseller + prompt) hazırlar. Kullanıcı Gemini uygulamasında sahne başına bir görsel üretir ve `--yerlestir` ile 1080×1920 boyutunda `sahneN_a.png` olarak yerleştirir. Kullanıcı gerektiğinde alternatif üretip `b` ve `c` varyantları olarak ekleyebilir.
4. ElevenLabs anlatımı cümle cümle seslendirir (her cümle önceki/sonraki cümleyi bağlam olarak görür, varsa `ton` etiketiyle, hız `sesler.json` → `hiz`: 1.2) ve kelime zamanlamalarını kaydeder; seçim kartını (soru + seçenekler) da anlatıcıya okutur. **Kontrol noktası:** Kullanıcı dinler, gerekirse tek bir cümleyi yeniden ürettirir.
5. ffmpeg videoyu birleştirir: görseller, ses, altyazı, ambiyans ve sonda anlatıcının okuduğu seçenek kartı; ses -14 LUFS'a normalleştirilir.
6. **Kapak (her bölümde, kalıcı kural):** `python kod/kapak.py bolumler/bolum_NN/senaryo.json` → `kapak.png` (Reels kapağı). Kapakta seri adı, "BÖLÜM N" (toplam bölüm sayısı yazılmaz, sürpriz kaçmasın), bölüm başlığı ve Bölüm 2'den itibaren önceki bölümde kazanan seçim ("Seçilen yol: A · …", `durum.json`'dan) yazar; yazılar profil ızgarasının orta 3:4 alanında kalır. Arka plan varsayılan sahne 1/a, `--gorsel 4=b` ile değişir. Testler: `python kod/test_kapak.py`.
7. Video kapakla birlikte yüklenir. Sonra kazanan seçim girilir ("B kazandı") ve `durum.json` güncellenir.

Hedef süre: kullanıcı başına bölüm başına 20–40 dk.

## Senaryo yazım kuralları (her bölüm, kalıcı)
Kaynak: "Seçmeli hikâye videolarını tutturma rehberi" (26.11.2026). Hikâyeye özel kurallar `hikaye.md`'de.
- **Açılış (ilk 2 sn):** İlk cümle soru ya da gerilim açar; sessizlik, selamlama, "bugünkü bölümde" yok. İlk 3 saniyede özel isim yerine rol kullanılır ("Rıza Usta" değil "şoför"). Sessiz izlendiğinde de merak uyandırmalı. **Kanca yazısı (kural 2026-11-28):** Her bölümde `kanca` alanı zorunlu (Bölüm 1 hariç, yayınlandı); en fazla 6 kelime, ilk kareden açılış sahnesinin (1. sahne) sonuna kadar ekranın üstünde durur. Anlatımı tekrar etmez, sessiz izleyene bir şey katar. `senaryo.py` Bölüm 2+ için kanca yoksa hata verir.
- **Kanca türleri, dönüşümlü:** sonuçtan başla · seçimin bedeli · gizemli nesne/ses · doğrudan soru · kural ihlali. Bölüm 2'den itibaren açılıştaki seçilmeyen yol sekansı "seçimin bedeli" kancası olarak yazılır; toplam 5 saniyeyi geçmez. Oy sonucu ("%62'niz B dedi") kural değil, bölüm bölüm kullanıcı karar verir (bkz. akış adım 1).
- **Tempo:** Sahne başına 4–8 sn (yaklaşık 10–20 kelime). Daha uzun bir an iki sahneye bölünür (ör. yakın plan/ayrıntı karesi). Gerilim anında kısa cümleler.
- **İkilem:** İki seçenek de bir şey kaybettirir (bariz doğru yok, hedef %50-50). Seçenek metni en fazla 4–5 kelime (anlatıcı kartta soruyu ve seçenekleri "A: …. B: …." diye okur; okunduğunda da doğal olmalı). Değer çatışması olur, bilgi testi değil. Seçim için gereken bilgi bölümde verilmiş olur. Üçüncü yol sunulmaz. Türler dönüşümlü: ahlaki, güven, risk, kaynak, merak.
- **Diyalog doğal konuşma dilinde (karar 2026-11-28):** Replikler yazı dili değil, konuşma dili ("Yok... görmedim.", "Bordo hırkalı?"); `...` duraksama verir. Her repliğe kısa İngilizce `ton` yazılır ("impatient, slightly annoyed"); seslendirmede `[ton]` etiketi olur, altyazıda görünmez. Sahne süresini korumak için daha uzun, gerçekçi diyaloglar yazılabilir.
- **Kapanış:** Son sahnenin son cümlesi ikilemi kurar. Mümkünse son kare açılış karesine görsel ya da sözel bağlanır (tekrar izlemede kopukluk olmasın).
- **Tutarlılık:** Özel isimlerin telaffuzu bir kez test edilir; sorunlu olan fonetik yazımla `hikaye.md`'ye kaydedilir ve hep öyle yazılır.
- **Seçimin sonucu hissedilir:** Kazanan seçim sonraki bölümde sahneyi, bir repliği ya da bir karakterin kaderini görünür biçimde değiştirir. İkilem yazılırken iki dalın kaba taslağı da çıkarılır.

## Üretim ve yayın standartları (rehberden, kalıcı)
Tam metin: `docs/rehber/secmeli-hikaye-rehberi-2026-11-26.pdf`. Yayın, oylama, metrik ve kontrol listesinin özeti beyin kasasında (`🏰 300-Projects/AI-Hikaye-Videolari/Yayin-Sureci.md`).
- **Kurgu:** Ekranda her 2–3 sn'de bir şey değişir. Zoom yönü sırayla değişir. Gerilimde kısa kesmeler + ses vuruşu. İlk 0.5 sn sessiz olmaz.
- **Altyazı:** büyük, kalın, 2–4 kelime; alt %20 ve sağ kenar boş. Anlatıcı beyaz, karakter konuşmaları karaktere özel renk, anahtar kelime vurgulu. ı/ş/ğ kontrol edilir.
- **Ses:** sesler sezon boyunca sabit; hız 1.2 (ElevenLabs `speed`; İngilizce ölçü olan 160–180 kelime/dk Türkçeye uymuyor, kulakla seçildi 2026-11-28); kanca cümlesi ayrı üretilip en iyisi seçilir; her sahnede en az bir ortam sesi; ikilem anında aynı 2 sn'lik "imza sesi" (henüz yok).
- **İkilem kartı:** 3–5 sn, A solda/kırmızı, B sağda/mavi; son karede "A mı, B mi? Yoruma yaz."; ayrı "takip et" kartı yok.
- **Görsel kontrol:** AI hatası (el, göz, eriyen yazı) olan varyant seçilmez.
- **Dışa aktarım:** 1080×1920, 30 fps, MP4 H.264; her platforma filigransız dosya. Her yayında AI etiketi açık; müzik kullanılırsa yalnız telifsiz/lisanslı.
- **Dallanma ve stok (karar 2026-11-27):** Seçim yalnız sonraki bölümün ilk 10–20 sn'lik seçime bağlı açılışını değiştirir; geri kalan ortak sahneler 2–3 bölüm stokta tutulur, açılış oylama kapanınca üretilir (ayrıntı: `hikaye.md` → "Dallanma noktaları").
- **Bilinçli olarak değiştirilmeyenler (karar 2026-11-27):** Sezon 8 bölüm kalır (rehber 10–12 öneriyor). ElevenLabs mevcut planla sürer.

## Klasör yapısı
```
hikaye-projesi/
├── .env                  # ELEVENLABS_API_KEY (git'e EKLENMEZ)
├── hikaye.md             # dünya, ton, karakter tarifleri, ana olay örgüsü, dallanma noktaları
├── durum.json            # bölüm özetleri + kazanan seçimler
├── varliklar/            # fontlar/ (altyazı fontu, OFL), ambiyans/ (mekân döngüleri, CC0)
├── karakterler/          # referans görseller (karakter sayfaları) + sesler.json (konuşan → ElevenLabs ses ID)
├── bolumler/bolum_01/    # senaryo.json, gorseller/, sesler/, video.mp4
└── kod/
    ├── senaryo.py        # senaryo.json şemasını doğrular (ileride: claude -p ile üretim)
    ├── gorsel.py         # görsel istekleri + yerleştirme (Gemini uygulaması, elle)
    ├── ses.py            # ElevenLabs (cümle sesleri + kelime zamanlamaları)
    ├── montaj.py         # ffmpeg (zoom, altyazı, seçenek kartı)
    ├── kapak.py          # Reels kapağı (seri, bölüm no, başlık, seçilen yol)
    └── yeni_bolum.py     # hepsini sırayla çalıştırır, kontrol noktalarında bekler
```

## Yol haritası
- [x] **Aşama 0:** Python 3.12 (`.venv`, uv ile), ffmpeg, `.env` (ElevenLabs), `.gitignore`. Kontrol: `.venv/bin/python kod/test_anahtarlar.py`
- [x] **Hikâye planı** (Planlama oturumu): tür, dünya, karakterler, ana olay örgüsü, dallanmalar → `hikaye.md`.
- [x] **1.** Senaryo JSON şeması + `senaryo.py` (şema doğrulama). Şema: `docs/superpowers/specs/2026-11-26-senaryo-semasi-design.md`. Kontrol: `python kod/senaryo.py bolumler/bolum_01/senaryo.json`, testler: `python kod/test_senaryo.py`. Diğer modüller `senaryo_yukle(yol)` kullanır.
- [x] **2.** `gorsel.py`: sahne başına bir ana görsel ve isteğe bağlı varyantlar, karakter referanslarıyla + stil örneği `karakterler/stil.png` (elle üretim, API yok). Tasarım: `docs/superpowers/specs/2026-11-26-gorsel-design.md`. Kontrol: `python kod/gorsel.py bolumler/bolum_01/senaryo.json --durum`, testler: `python kod/test_gorsel.py`.
- [x] **3.** `ses.py`: cümle bazlı TTS (ElevenLabs `eleven_v4`) + kelime zamanlamaları (`sesler/zamanlama.json`). Tam bölümde seçim kartı okuması da üretilir (`sesler/kart.mp3`, anlatıcı sesi; yeniden üretmek için `--kart`). Cümle başına isteğe bağlı `ton` → `[ton]` etiketi (hizalamadan ayıklanır), `previous_text`/`next_text` ile komşu cümleler, `hiz` ile `voice_settings.speed`; `hiz` alanı olmayan eski kayıtlar (Bölüm 1–2) hazır sayılır. Konuşan → ses eşlemesi `karakterler/sesler.json` (ücretsiz planda yalnızca hazır sesler; dinlenerek seçildi). Tasarım: `docs/superpowers/specs/2026-11-26-ses-design.md`. Kontrol: `python kod/ses.py bolumler/bolum_01/senaryo.json --kuru`, testler: `python kod/test_ses.py`.
- [x] **4.** `montaj.py`: 1080×1920, sahne başına yavaş zoom, kelime vurgulu altyazı (font `varliklar/fontlar/`), sonda seçenek kartı (anlatıcı okur, kart okuma bitene kadar uzar; okuma yoksa sessiz kalır ve uyarı verilir); müzik yok. `kanca` ilk kareden 1. sahnenin sonuna kadar üstte küçük yazı. Ses sonda iki geçişli loudnorm ile -14 LUFS'a getirilir (video yeniden kodlanmaz). Ambiyans: sahnenin `mekan`ına göre `varliklar/ambiyans/<mekan>.mp3` döngüsü (freesound CC0, kaynaklar `KAYNAKLAR.md`; yeni kayıt `kod/ambiyans_hazirla.py` ile hazırlanır), konuşurken kısılır. Görsel varyantı varsayılan `a`, `--varyant 3=b`. Tasarım: `docs/superpowers/specs/2026-11-26-montaj-design.md`. Kontrol: `python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 3` (→ `onizleme.mp4`; tam bölüm → `video.mp4`), testler: `python kod/test_montaj.py`.
- [x] **5.** `yeni_bolum.py`: orkestrasyon ve kontrol noktaları (varyant seçimi dahil). Başta her adım (görsel, ses, montaj, kapak) için sorar: `s` sistem yapar (Enter), `k` kendim (komutu gösterir, Enter bekler), `a` atla; yanında adımın mevcut durumu yazar. Her girdide `dur` ile çıkılır. Modüller ayrı süreç olarak çalışır. Kontrol: `python kod/yeni_bolum.py bolumler/bolum_02/senaryo.json`, testler: `python kod/test_yeni_bolum.py`. Henüz yok: kazanan seçimin `durum.json`'a girilmesi (elle).

Oturum düzeni (ayrıntı: `KULLANIM.md`): **Planlama** = hikâye kararları, **Kod** = pipeline modülleri, **Bölümler** = bölüm başına üretim.
Kullanıcı yeni bir cihazda **"oturum düzenini kur"** derse: `KULLANIM.md` → "Oturum düzeni" bölümündeki adımları uygula.

İlke: Her modül tek başına çalışmalı ve test edilebilmeli. Önce bir bölümü baştan sona çıkaran basit bir sürüm kurulacak, sonra geliştirilecek.

## Notlar
- Anthropic API bilinçli olarak kullanılmıyor (ayrı faturalandığı için). Senaryo Pro aboneliğiyle Claude Code'da yazılır.
- Gerçekçi yapay zekâ içeriği TikTok'ta "AI-generated" olarak etiketlenmeli.
- Ana olay örgüsü önceden planlanır, seçimler ayrıntıları değiştirir. Böylece hikâye dağılmaz.
- Güncel model adlarını ve SDK sürümlerini kodu yazmadan önce resmi dokümanlardan doğrula.
- **Ambiyans:** Döngüler freesound CC0 gerçek kayıtlarından (kredi harcamaz). Tek seferlik efektler (retarder, kapı, gerilim vurgusu) ileride ElevenLabs ses efektiyle eklenebilir (kredi harcar; henüz yapılmadı). `istasyon` mekânının ambiyansı yok (Bölüm 6'dan önce eklenmeli; yoksa o sahneler uyarıyla sessiz kalır).
