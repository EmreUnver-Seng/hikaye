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

## Alınmış kararlar
- **Araçlar:** Claude (senaryo; **API kullanılmaz**, Claude Code üzerinden Pro aboneliğiyle), Gemini (görsel; isteğe bağlı Veo ile kısa klip), ElevenLabs (seslendirme; istenirse efekt ve müzik).
- **Çalışma şekli:** Yarı otomatik. Kod tekrar eden işleri yapar (API çağrıları, dosya indirme ve adlandırma, montaj, altyazı, durum kaydı). Yaratıcı kararları kullanıcı verir.
- **Görsel stil:** 2 boyutlu, basit karakterler (düz renk, kalın hat). Tutarlılık için karakter referans görselleri her istekte gönderilir.
- **Format:** Dikey 9:16, bölüm başına 45–90 sn, 8–12 sahne, altyazılı.
- **Tür:** Henüz seçilmedi. Adaylar: gerilim/gizem, hayatta kalma, kara komedi.

## Bir bölümün akışı (kullanıcının gözünden)
1. Kullanıcı Claude Code'a "Bölüm N'in senaryosunu yaz" der. Claude `hikaye.md` ve `durum.json` dosyalarını okuyup `bolumler/bolum_NN/senaryo.json` dosyasını yazar. (İleride `senaryo.py` bunu `claude -p` ile otomatik yapabilir.) **Kontrol noktası:** Kullanıcı senaryoyu okuyup düzenler.
2. `python kod/yeni_bolum.py` komutu çalıştırılır; mevcut `senaryo.json` dosyasını girdi olarak alır.
3. Gemini her sahne için 3 görsel üretir (`sahneN_a/b/c.png`). **Kontrol noktası:** Kullanıcı her sahne için birini seçer veya yeniden ürettirir.
4. ElevenLabs anlatımı cümle cümle seslendirir ve kelime zamanlamalarını kaydeder. **Kontrol noktası:** Kullanıcı dinler, gerekirse tek bir cümleyi yeniden ürettirir.
5. ffmpeg videoyu birleştirir: görseller, ses, altyazı, müzik ve sonda seçenek kartı.
6. Video yüklenir. Sonra kazanan seçim girilir ("B kazandı") ve `durum.json` güncellenir.

Hedef süre: kullanıcı başına bölüm başına 20–40 dk.

## Klasör yapısı
```
hikaye-projesi/
├── .env                  # GEMINI_API_KEY, ELEVENLABS_API_KEY (git'e EKLENMEZ)
├── hikaye.md             # dünya, ton, karakter tarifleri, ana olay örgüsü, dallanma noktaları
├── durum.json            # bölüm özetleri + kazanan seçimler
├── karakterler/          # referans görseller (karakter sayfaları)
├── bolumler/bolum_01/    # senaryo.json, gorseller/, sesler/, video.mp4
└── kod/
    ├── senaryo.py        # senaryo.json şemasını doğrular (ileride: claude -p ile üretim)
    ├── gorsel.py         # Gemini
    ├── ses.py            # ElevenLabs
    ├── montaj.py         # ffmpeg
    └── yeni_bolum.py     # hepsini sırayla çalıştırır, kontrol noktalarında bekler
```

## Yol haritası
- [x] **Aşama 0:** Python 3.12 (`.venv`, uv ile), ffmpeg, `.env` (Gemini + ElevenLabs), `.gitignore`. Kontrol: `.venv/bin/python kod/test_anahtarlar.py`
- [ ] **Hikâye planı** (Planlama oturumu, kodla paralel): tür, dünya, karakterler, ana olay örgüsü, dallanmalar → `hikaye.md`. ← **SIRADAKİ ADIM**
- [ ] **1.** Senaryo JSON şeması + `senaryo.py` (şema doğrulama). `hikaye.md` şablonu hazır.
- [ ] **2.** `gorsel.py`: sahne başına 3 varyant, karakter referanslarıyla.
- [ ] **3.** `ses.py`: cümle bazlı TTS + zaman damgaları, sabit ses ID'si.
- [ ] **4.** `montaj.py`: 9:16, yavaş zoom, altyazı, müzik, seçenek kartı.
- [ ] **5.** `yeni_bolum.py`: orkestrasyon ve kontrol noktaları.

Oturum düzeni (ayrıntı: `KULLANIM.md`): **Planlama** = hikâye kararları, **Kod** = pipeline modülleri, **Bölümler** = bölüm başına üretim.

İlke: Her modül tek başına çalışmalı ve test edilebilmeli. Önce bir bölümü baştan sona çıkaran basit bir sürüm kurulacak, sonra geliştirilecek.

## Notlar
- Anthropic API bilinçli olarak kullanılmıyor (ayrı faturalandığı için). Senaryo Pro aboneliğiyle Claude Code'da yazılır.
- Gerçekçi yapay zekâ içeriği TikTok'ta "AI-generated" olarak etiketlenmeli.
- Ana olay örgüsü önceden planlanır, seçimler ayrıntıları değiştirir. Böylece hikâye dağılmaz.
- Güncel model adlarını ve SDK sürümlerini kodu yazmadan önce resmi dokümanlardan doğrula.
