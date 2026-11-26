# Görsel adımı: `gorsel.py` (Yol haritası adım 2)

## Amaç
Her sahne için 3 görsel varyant (`bolumler/bolum_NN/gorseller/sahneN_a/b/c.png`), karakterler bölümden bölüme tutarlı. Kullanılmayan varyantlar ileriki bölümler için ilham arşivi olarak kalır.

## Kararlar (kullanıcıyla)
- **Sistem ücretsiz kalacak.** Gemini API'de görsel üretimi ücretli (fiyat tablosunda tüm görsel modelleri için "Free Tier: Not available", Kasım 2026). Bu yüzden **Gemini API hiçbir yerde kullanılmaz**; görseller kullanıcı tarafından **Gemini uygulamasında elle** üretilir.
- `gorsel.py` görsel üretmez. İki iş yapar: (1) her sahne için hazır istek (eklenecek referans görseller + yapıştırılacak prompt), (2) indirilen dosyaları doğru ada ve boyuta yerleştirme.
- **Her sahne için 3 varyant** (a, b, c) her zaman üretilir.
- **Karakter referansları** (`karakterler/<kimlik>.png`) aynı yoldan üretilir: `--karakter <kimlik>` istek verir, seçilen görsel `--yerlestir` ile yerine konur. Tarif `hikaye.md`'den okunur (tek kaynak, kopyalanmaz).
- **Referans eksikse** sahne isteği yazılmaz; eksik karakterler ve çalıştırılacak `--karakter` komutu söylenir.
- Varyantlardan hangisinin seçildiği adım 5'in (`yeni_bolum.py`) işi; bu modül yalnızca hazırlar ve yerleştirir.

## Yaklaşımlar
- **Seçilen — elle üretim + yardımcı araç:** Ücretsiz. Kod tekrar eden işi (prompt kurma, adlandırma, kesme, durum) yapar; kullanıcı yalnızca kopyala-yapıştır ve indir yapar.
- **Elenen — Gemini API (`gemini-3.1-flash-image`):** Tam otomatik ama bölüm başına ~2 $. Ücretsiz kalma hedefine aykırı.
- **Elenen — tamamen elle (kod yok):** Dosya adlandırma, 9:16 kesim ve referans takibi her bölümde elle yapılır; hata çıkar.

## Kullanım
```
python kod/gorsel.py bolumler/bolum_01/senaryo.json                 # istekleri yaz + durum
python kod/gorsel.py bolumler/bolum_01/senaryo.json --karakter riza # karakter sayfası isteği
python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir 3 [dosya ...]
python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir riza [dosya]
python kod/gorsel.py bolumler/bolum_01/senaryo.json --durum
```
- **İstekler:** Ekrana ve `gorseller/istekler.md`'ye yazılır. Her sahne: başlık, eklenecek referans dosyaları (sırasıyla), kod bloğunda prompt. Referansı eksik karakter varsa sahne isteği yerine uyarı ve komut yazılır.
- **Stil referansı:** `karakterler/stil.png` (kullanıcının verdiği örnek; yalnızca çizim tarzı ve detay seviyesi, görünüş değil). Varsa her sahne ve karakter isteğinde **en sona** eklenir, prompt'ta "yalnızca çizim tarzı için örnek; kişiyi, kıyafeti, mekânı kullanma" denir. `--yerlestir stil <dosya>` ile konur. (Kullanıcı ilk denemeden sonra "biraz daha detaylı" istedi; ilk tarif düz renk/kalın hat idi.)
- **Mekân:** Sahnede `mekan` varsa `hikaye.md`'deki mekân maddesi + renk paleti satırı prompt'a "Mekân:" olarak eklenir (parantez içi yazar notları çıkarılır). Sebep: Bölüm 1 sahne 3'te tarif koltuk rengini söylemediği için Gemini kahverengi koltuk çizdi. Ayrıca "pozlara, hareketlere ve bakış yönüne birebir uy" satırı eklenir (aynı sahnede Nadide'nin arkaya bakışı kaybolmuştu).
- **Prompt:** Sabit stil (2B dijital çizgi film, temiz koyu kontur, iki tonlu gölgelendirme, saç/yüz/kumaşta orta seviye detay, fotogerçekçi değil, dikey 9:16, yazı/altyazı/konuşma balonu yok; sahnelerde loş sinematik ışık, karakter sayfalarında nötr ışık). Her prompt son satırda **3 farklı görsel** ister (sahnede kamera açısı/kompozisyon, karakter sayfasında ifade/duruş farklı; görünüş aynı) + "Ekteki 1. görsel: Sen — <görünüş>" satırları + sahnenin `gorsel` tarifi.
- **Yerleştirme (sahne):** Dosyalar sahnenin ilk boş harflerine (a, b, c) sırayla yerleşir. Üç harf doluysa hata; `--yeniden` ile a'dan başlayarak üzerine yazılır. ffmpeg ile **1080×1920'ye** ölçeklenip ortadan kesilir. Kaynak oranı 9:16'dan çok farklıysa (>%10) uyarı verilir (kesimde çok şey kaybolur).
- **Yerleştirme (karakter):** Tek dosya, PNG'ye çevrilir, kesilmez. Var olan referansın üzerine yalnızca `--yeniden` ile yazılır.
- **Dosya verilmezse:** İndirilenler klasöründeki (`Path.home() / "Downloads"`) en yeni görseller (gereken sayıda) listelenir ve onay (e/h) istenir.
- **Durum:** Sahne başına kaç varyant hazır, hangi referanslar eksik.

## Proje geneline etkiler
- `CLAUDE.md`: Araçlar, akış (adım 3), klasör yapısı ve yol haritası Gemini API yerine elle üretimi anlatır; Veo çıkar.
- `requirements.txt`'ten `google-genai`, `.env.example`'dan `GEMINI_API_KEY` çıkar; `test_anahtarlar.py` ve `kurulum_kontrol.py` Gemini kontrolünü bırakır.
- `KULLANIM.md` bölüm üretimi listesine görsel adımları eklenir.

## Test
`kod/test_gorsel.py` (düz Python, API ve ağ yok): `hikaye.md`'den tarif okuma, prompt içeriği, referans seçimi ve eksik referans, dosya adları ve boş harf seçimi, `--yeniden`, oran uyarısı hesabı. ffmpeg'li yerleştirme geçici klasörde küçük bir test görseliyle denenir (ffmpeg yoksa atlanır).
Gerçek deneme: `sen` karakter sayfası + Bölüm 1 sahne 1, kullanıcının Gemini uygulamasında ürettiği görsellerle.
