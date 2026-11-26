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
- **Görsel stil:** 2 boyutlu dijital çizgi film; temiz koyu kontur, iki tonlu gölgelendirme, orta seviye detay (fotogerçekçi değil). Tarz örneği `karakterler/stil.png` her istekte en sona eklenir. Tutarlılık için karakter referans görselleri de her istekte gönderilir.
- **Format:** Dikey 9:16, bölüm başına 45–90 sn, 8–12 sahne, altyazılı.
- **Tür:** Gerilim/gizem. Hikâye: "Son Durak" (8 bölüm, gece otobüsü, "sen" diye hitap eden anlatıcı). Ayrıntı: `hikaye.md`.

## Bir bölümün akışı (kullanıcının gözünden)
1. Kullanıcı Claude Code'a "Bölüm N'in senaryosunu yaz" der. Claude `hikaye.md` ve `durum.json` dosyalarını okuyup `bolumler/bolum_NN/senaryo.json` dosyasını yazar. (İleride `senaryo.py` bunu `claude -p` ile otomatik yapabilir.) **Kontrol noktası:** Kullanıcı senaryoyu okuyup düzenler.
2. `python kod/yeni_bolum.py` komutu çalıştırılır; mevcut `senaryo.json` dosyasını girdi olarak alır.
3. `gorsel.py` her sahne için istek (referans görseller + prompt) hazırlar; kullanıcı Gemini uygulamasında sahne başına 3 görsel üretir, `--yerlestir` ile `sahneN_a/b/c.png` olarak 1080×1920'ye kesilip yerleşir. **Kontrol noktası:** Kullanıcı her sahne için birini seçer veya yeniden üretir. Seçilmeyenler ilham arşivi olarak kalır.
4. ElevenLabs anlatımı cümle cümle seslendirir ve kelime zamanlamalarını kaydeder. **Kontrol noktası:** Kullanıcı dinler, gerekirse tek bir cümleyi yeniden ürettirir.
5. ffmpeg videoyu birleştirir: görseller, ses, altyazı, müzik ve sonda seçenek kartı.
6. **Kapak (her bölümde, kalıcı kural):** `python kod/kapak.py bolumler/bolum_NN/senaryo.json` → `kapak.png` (Reels kapağı). Kapakta seri adı, "BÖLÜM N" (toplam bölüm sayısı yazılmaz, sürpriz kaçmasın), bölüm başlığı ve Bölüm 2'den itibaren önceki bölümde kazanan seçim ("Seçilen yol: A · …", `durum.json`'dan) yazar; yazılar profil ızgarasının orta 3:4 alanında kalır. Arka plan varsayılan sahne 1/a, `--gorsel 4=b` ile değişir. Testler: `python kod/test_kapak.py`.
7. Video kapakla birlikte yüklenir. Sonra kazanan seçim girilir ("B kazandı") ve `durum.json` güncellenir.

Hedef süre: kullanıcı başına bölüm başına 20–40 dk.

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
- [x] **2.** `gorsel.py`: sahne başına 3 varyant, karakter referanslarıyla + stil örneği `karakterler/stil.png` (elle üretim, API yok). Tasarım: `docs/superpowers/specs/2026-11-26-gorsel-design.md`. Kontrol: `python kod/gorsel.py bolumler/bolum_01/senaryo.json --durum`, testler: `python kod/test_gorsel.py`.
- [x] **3.** `ses.py`: cümle bazlı TTS (ElevenLabs `eleven_v4`) + kelime zamanlamaları (`sesler/zamanlama.json`). Konuşan → ses eşlemesi `karakterler/sesler.json` (ücretsiz planda yalnızca hazır sesler; dinlenerek seçildi). Tasarım: `docs/superpowers/specs/2026-11-26-ses-design.md`. Kontrol: `python kod/ses.py bolumler/bolum_01/senaryo.json --kuru`, testler: `python kod/test_ses.py`.
- [x] **4.** `montaj.py`: 1080×1920, sahne başına yavaş zoom, kelime vurgulu altyazı (font `varliklar/fontlar/`), sonda seçenek kartı; müzik yok. Ambiyans: sahnenin `mekan`ına göre `varliklar/ambiyans/<mekan>.mp3` döngüsü (freesound CC0, kaynaklar `KAYNAKLAR.md`; yeni kayıt `kod/ambiyans_hazirla.py` ile hazırlanır), konuşurken kısılır. Görsel varyantı varsayılan `a`, `--varyant 3=b`. Tasarım: `docs/superpowers/specs/2026-11-26-montaj-design.md`. Kontrol: `python kod/montaj.py bolumler/bolum_01/senaryo.json --sahne 3` (→ `onizleme.mp4`; tam bölüm → `video.mp4`), testler: `python kod/test_montaj.py`.
- [ ] **5.** `yeni_bolum.py`: orkestrasyon ve kontrol noktaları (varyant seçimi dahil). ← **SIRADAKİ ADIM**

Oturum düzeni (ayrıntı: `KULLANIM.md`): **Planlama** = hikâye kararları, **Kod** = pipeline modülleri, **Bölümler** = bölüm başına üretim.
Kullanıcı yeni bir cihazda **"oturum düzenini kur"** derse: `KULLANIM.md` → "Oturum düzeni" bölümündeki adımları uygula.

İlke: Her modül tek başına çalışmalı ve test edilebilmeli. Önce bir bölümü baştan sona çıkaran basit bir sürüm kurulacak, sonra geliştirilecek.

## Notlar
- Anthropic API bilinçli olarak kullanılmıyor (ayrı faturalandığı için). Senaryo Pro aboneliğiyle Claude Code'da yazılır.
- Gerçekçi yapay zekâ içeriği TikTok'ta "AI-generated" olarak etiketlenmeli.
- Ana olay örgüsü önceden planlanır, seçimler ayrıntıları değiştirir. Böylece hikâye dağılmaz.
- Güncel model adlarını ve SDK sürümlerini kodu yazmadan önce resmi dokümanlardan doğrula.
- **Ambiyans:** Döngüler freesound CC0 gerçek kayıtlarından (kredi harcamaz). Tek seferlik efektler (retarder, kapı, gerilim vurgusu) ileride ElevenLabs ses efektiyle eklenebilir (kredi harcar; henüz yapılmadı). `istasyon` mekânının ambiyansı yok (Bölüm 6'dan önce eklenmeli; yoksa o sahneler uyarıyla sessiz kalır).
