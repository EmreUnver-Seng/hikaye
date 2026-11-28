# Son Durak

Instagram Reels ve TikTok için izleyici seçimleriyle ilerleyen kısa hikâye videoları üreten yarı otomatik bir Python pipeline’ı. Her bölüm bir A/B ikilemiyle biter. Yayından sonra kazanan seçim `durum.json` dosyasına işlenir ve sonraki bölümün senaryosuna yön verir.

## Bir bölüm nasıl üretilir?

1. **Senaryo.** Claude Code, `hikaye.md` ve `durum.json` dosyalarından bölümün `senaryo.json` dosyasını hazırlar. Senaryo gözden geçirildikten sonra üretim başlatılır.
2. **Görseller.** Pipeline, her sahne için karakter referanslarıyla birlikte bir görsel istemi hazırlar. Görseller Gemini uygulamasında elle üretilir ve bölüm klasörüne yerleştirilir.
3. **Ses.** ElevenLabs, replikleri önceki ve sonraki cümlelerin bağlamıyla, varsa ton etiketiyle ve 1,2× hızda seslendirir. Seçim kartını da okur ve altyazı için sözcük zamanlamaları döndürür.
4. **Montaj ve kapak.** FFmpeg görselleri, seslendirmeyi, altyazıyı ve ambiyansı birleştirir, seçim kartını sona ekler. Bölüm klasöründe 1080 × 1920 boyutunda `video.mp4` ve paylaşım için `kapak.png` oluşur. Yayın elle yapılır.

## Çalıştırma

Python 3.12 ve PATH üzerinde FFmpeg gerekir. `.env.example` dosyasını `.env` olarak kopyalayıp `ELEVENLABS_API_KEY` değerini gir. Ardından repo kökünden, hazır bir bölüm senaryosuyla çalıştır:

```sh
python -m pip install -r requirements.txt
python kod/yeni_bolum.py bolumler/bolum_02/senaryo.json
```

Komut görsel, ses, montaj ve kapak adımlarını etkileşimli olarak yürütür. Tek sahne önizleme ve tek repliği yeniden üretme komutları için [kullanım kılavuzuna](KULLANIM.md) bak.
