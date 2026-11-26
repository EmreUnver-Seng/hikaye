# Ses adımı: `ses.py` (Yol haritası adım 3)

## Amaç
Senaryodaki her cümleyi konuşanın sabit ElevenLabs sesiyle seslendirmek ve altyazı için kelime zamanlamalarını kaydetmek. Çıktılar `bolumler/bolum_NN/sesler/` klasörüne gider; `montaj.py` (adım 4) bu dosyaları kullanır.

## Kararlar (kullanıcıyla)
- **Sistem ücretsiz kalacak.** ElevenLabs ücretsiz plan: ayda 10.000 kredi. Ücretsiz planda Ses Kütüphanesi (topluluk) sesleri API'den kullanılamaz; yalnızca hazır (premade) sesler var. Hepsi İngilizce etiketli, Türkçeyi çok dilli model konuşturur.
- **Sesler dinlenerek seçildi** (deneme, Kasım 2026, ~580 kredi). Hepsi `eleven_v4` ile:
  | Konuşan | Ses | ID |
  |---|---|---|
  | anlatici | George | `JBFqnCBsd6RMkjVDRZzb` |
  | fatma | Lily | `pFZP5JQG7iQjIQuC4Bku` |
  | kerem | Liam | `TX3LPaxmHKxFdv7VOQHJ` |
  | murat | Daniel | `onwK4e9ZLuTAKqWW03F9` |
  | sen | Charlie | `IKne3meq5aSn9XLyUdCD` |
  Murat için Eric ve Adam aksan yüzünden elendi. Rıza ve Ayla Bölüm 1'de konuşmuyor; sesleri ilk konuştukları bölümden önce aynı yolla (kısa deneme) seçilecek.
- **Model:** `eleven_v4` (en kaliteli, Türkçe destekli, 1 kredi/karakter, zaman damgalı uç noktada denendi ve çalışıyor). Bölüm 1 ≈ 860 karakter → ayda ~11 bölüm. Kota daralırsa `eleven_flash_v2_5` (0,5 kredi/karakter) yalnızca `sesler.json`'daki model değiştirilerek kullanılabilir.
- **Tek cümleyi yeniden üretme** `--cumle S.C` ile.
- **Var olan sesler atlanır;** metin, ses veya model değiştiyse o cümle yeniden üretilir.
- **Numarası kayan cümle yeniden ücretlenmez** (son incelemede eklendi): sahneye cümle eklenip silinince sonraki cümlelerin anahtarı değişir; aynı metin + ses + modelle hazır başka bir kayıt varsa ses API'siz kopyalanır. Kopyalar üretimden önce, tüm kaynaklar belleğe okunduktan sonra yazılır (zincirleme kayma için). `--cumle` her zaman gerçekten üretir.
- **Ses ID'si eksikse** hiç API çağrısı yapılmaz.
- **Kota koruması:** her harcamadan önce karakter sayısı ve kalan kota gösterilir, onay (e/h) istenir; `--kuru` hiçbir ses üretmez.
- **Bilinçli olarak yok:** `previous_text`/`next_text` (cümleler arası tonlama bağlamı; ek kredi harcatıp harcatmadığı dokümanda yazmıyor) ve özel ses ayarları (varsayılanlar kullanılır). İleride eklenebilir.

## Yaklaşımlar
- **Seçilen — cümle başına bir çağrı:** Konuşan cümle cümle değişiyor; tek cümleyi yeniden üretmek ve değişeni bulmak kolay. Montaj cümle dosyalarını uç uca ekler.
- **Elenen — sahne başına tek çağrı:** Sahnede birden fazla konuşan var, tek sesle olmaz; tek cümle düzeltmesi tüm sahneyi yeniden harcatır.
- **Elenen — Text to Dialogue API (çok sesli tek istek):** Tek cümle yenilemek yine tüm diyaloğu harcatır, kelime zamanlaması/atlama mantığı karmaşıklaşır.

## Ses eşlemesi: `karakterler/sesler.json` (git'e girer, gizli değil)
```json
{
  "model": "eleven_v4",
  "sesler": {
    "anlatici": {"id": "JBFqnCBsd6RMkjVDRZzb", "ad": "George"},
    "fatma":   {"id": "pFZP5JQG7iQjIQuC4Bku", "ad": "Lily"},
    "kerem":    {"id": "TX3LPaxmHKxFdv7VOQHJ", "ad": "Liam"},
    "murat":    {"id": "onwK4e9ZLuTAKqWW03F9", "ad": "Daniel"},
    "sen":      {"id": "IKne3meq5aSn9XLyUdCD", "ad": "Charlie"}
  }
}
```
Doğrulama: `model` boş olmayan metin; `sesler` anahtarları `anlatici` veya bilinen karakter kimlikleri (`senaryo.KARAKTERLER`); her değerde boş olmayan `id` metni; `ad` isteğe bağlı (insan için). Hatalar Türkçe ve hepsi birden listelenir.

## Çıktılar (`bolumler/bolum_NN/sesler/`)
- `s03_c2.mp3`: sahne 3'ün 2. cümlesi (sahne iki haneli, cümle 1'den sayılır). Biçim `mp3_44100_128` (ücretsiz planda izinli).
- `zamanlama.json`:
```json
{
  "bolum": 1,
  "cumleler": {
    "s03_c2": {
      "sahne": 3, "cumle": 2, "konusan": "anlatici",
      "metin": "Çok konuşuyor. Ama konuşurken sürekli arkaya bakıyor.",
      "ses_id": "JBFqnCBsd6RMkjVDRZzb", "model": "eleven_v4",
      "dosya": "s03_c2.mp3", "sure": 3.41,
      "kelimeler": [{"kelime": "Çok", "baslangic": 0.0, "bitis": 0.31}, "..."]
    }
  }
}
```
- **Kelimeler:** API'nin `alignment` alanındaki harf zamanlamalarından çıkarılır (yoksa `normalized_alignment`). Boşluklarda bölünür; noktalama kelimeye yapışık kalır (altyazı metni aynen gösterir). `baslangic` = ilk harfin başlangıcı, `bitis` = son harfin bitişi. `sure` = son harfin bitişi. İkisi de yoksa hata.
- `zamanlama.json` **her cümleden sonra** atomik olarak kaydedilir (geçici dosya + `replace`): API yarıda hata verirse yeniden çalıştırınca kaldığı yerden devam eder.
- `sesler/deneme/` gibi alt klasörlere dokunulmaz. Senaryoda artık olmayan kayıtlar silinmez, yalnızca uyarı verilir.

## Kullanım
```
python kod/ses.py bolumler/bolum_01/senaryo.json              # eksik ve değişen cümleleri üret
python kod/ses.py bolumler/bolum_01/senaryo.json --sahne 3    # yalnızca 3. sahne
python kod/ses.py bolumler/bolum_01/senaryo.json --cumle 3.2  # tek cümleyi (var olsa da) yeniden üret
python kod/ses.py bolumler/bolum_01/senaryo.json --kuru       # ses üretmez: ne üretilecek, kaç karakter, kalan kota
```
`--sahne` ve `--cumle` birlikte verilmez. Olmayan sahne/cümle numarası hata.

**Akış:**
1. `senaryo_yukle(yol)` (geçersizse `senaryo.py` mesajları gösterilir, çıkış 1).
2. `karakterler/sesler.json` okunur ve doğrulanır.
3. Kapsamdaki cümleler için iş listesi: dosya + kayıt var ve `metin`, `ses_id`, `model` aynıysa **atla**; değilse **üret**. `--cumle` her zaman üretir.
4. Kapsamda `sesler.json`'da sesi olmayan konuşan varsa: eksiklerin listesi + "karakterler/sesler.json'a ekle" mesajı, API çağrısı yok, çıkış 1.
5. Üretilecek yoksa "Hepsi hazır" ve çıkış 0.
6. Özet: "N cümle üretilecek, M atlanacak, X karakter harcanacak. Kalan kota: Y/Z." Kota `user.subscription.get()` ile (ücretsiz çağrı): kalan = `character_limit - character_count`. X > kalan ise hata, çıkış 1. `--kuru` burada durur (anahtar yoksa kota "bilinmiyor" der, yine sayar).
7. "Devam edilsin mi? (e/h)". `h` → çıkış 0, hiçbir şey harcanmaz.
8. Her cümle: `text_to_speech.convert_with_timestamps(ses_id, text=metin, model_id=model, language_code="tr", output_format="mp3_44100_128")`; `language_code` model `eleven_multilingual_v2` ise gönderilmez (o model desteklemiyor). `audio_base_64` çözülüp mp3 yazılır, kelimeler çıkarılır, kayıt güncellenir. Ekrana `✓ s03_c2 (anlatici, 3.4 sn)`.
9. Sonda: üretilen/atlanan sayısı, bölümün toplam ses süresi.

**Hatalar** (Türkçe, çıkış 1): `.env`'de `ELEVENLABS_API_KEY` yok; API hatası (401 → anahtar geçersiz; kota aşıldı; ses bulunamadı → `sesler.json`'daki ID'yi kontrol et; diğerleri durum kodu + kısa mesaj). Anahtar hiçbir zaman ekrana yazılmaz. Hata anında o ana kadar üretilenler kayıtlı kalır.

## Çapraz platform
`pathlib.Path`, tüm dosyalar `encoding="utf-8"`, `sys.stdout.reconfigure(encoding="utf-8")` (Windows konsolu). ffmpeg gerekmez.

## Test: `kod/test_ses.py` (düz Python, ağ yok)
API istemcisi parametre olarak verilir; testler sahte istemci kullanır (sabit mp3 baytı + gerçek biçimde alignment, sayaç). Denenenler: `sesler.json` doğrulama (eksik alan, bilinmeyen kimlik, boş id); dosya adları; iş listesi (atlama, metin/ses/model değişince yeniden, `--sahne`, `--cumle`, olmayan numara); karakter sayımı; eksik ses ID'sinde API'nin hiç çağrılmaması; kota yetmezse çağrılmaması; `h` cevabında çağrılmaması; kelime çıkarma (Türkçe harfler, noktalama, çoklu boşluk; deneme klasöründeki gerçek George cevabının biçimi); yarıda hata sonrası önceki kayıtların korunması.

**Gerçek deneme:** Bölüm 1, sahne 3 (Fatma + anlatıcı, ~114 kredi).

## Proje geneline etkiler
- `CLAUDE.md`: yol haritasında adım 3 işaretlenir, kontrol komutu ve `sesler.json` notu eklenir.
- `KULLANIM.md` bölüm üretimi listesine ses adımı (`--kuru`, sonra üretim, dinleme, `--cumle`) ve yeni karakter konuşunca ses seçme notu eklenir.

## Uygulayıcıya bırakılanlar
İç fonksiyon adları ve bölümlemesi, mesajların tam metni, atomik yazma ayrıntısı.
