# Görsel adımı: `gorsel.py` (Yol haritası adım 2)

## Amaç
Her sahne için bir ana görsel (`bolumler/bolum_NN/gorseller/sahneN_a.png`) üretilir ve karakterler bölümden bölüme tutarlı kalır. Kullanılmayan varyantlar ileriki bölümler için ilham arşivi olarak kalır.

## Kararlar (kullanıcıyla)
- **Sistem ücretsiz kalacak.** Gemini API'de görsel üretimi ücretli (fiyat tablosunda tüm görsel modelleri için "Free Tier: Not available", Kasım 2026). Bu yüzden **Gemini API hiçbir yerde kullanılmaz**; görseller kullanıcı tarafından **Gemini uygulamasında elle** üretilir.
- `gorsel.py` görsel üretmez. İki iş yapar: (1) her sahne için hazır istek (eklenecek referans görseller + yapıştırılacak prompt), (2) indirilen dosyaları doğru ada ve boyuta yerleştirme.
- **Her sahne için tek ana görsel** (`a`) üretilir. Kullanıcı gerektiğinde `b` ve `c` alternatiflerini ekleyebilir.
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
python kod/gorsel.py bolumler/bolum_01/senaryo.json --yerlestir secenekA [dosya]
python kod/gorsel.py bolumler/bolum_01/senaryo.json --durum
```
- **İstekler:** Ekrana ve `gorseller/istekler.md`'ye yazılır. Her sahne: başlık, eklenecek referans dosyaları (sırasıyla), kod bloğunda prompt. Referansı eksik karakter varsa sahne isteği yerine uyarı ve komut yazılır.
- **Stil referansı:** `karakterler/stil.png` (kullanıcının verdiği örnek; yalnızca çizim tarzı ve detay seviyesi, görünüş değil). Karakter sayfası ve seçim kartı isteklerine, ayrıca `stil-sahne.png` eksikse sahne isteklerine **en sona** eklenir, prompt'ta "yalnızca çizim tarzı için örnek; kişiyi, kıyafeti, mekânı kullanma" denir. `--yerlestir stil <dosya>` ile konur. (Kullanıcı ilk denemeden sonra "biraz daha detaylı" istedi; ilk tarif düz renk/kalın hat idi.)
- **Mekân:** Sahnede `mekan` varsa `hikaye.md`'deki mekân maddesi + renk paleti satırı prompt'a "Mekân:" olarak eklenir (parantez içi yazar notları çıkarılır). Sebep: Bölüm 1 sahne 3'te tarif koltuk rengini söylemediği için Gemini kahverengi koltuk çizdi. Ayrıca "pozlara, hareketlere ve bakış yönüne birebir uy" satırı eklenir (aynı sahnede Fatma'nın arkaya bakışı kaybolmuştu).
- **Prompt:** Sabit stil (2B dijital çizgi film, temiz koyu kontur, iki tonlu gölgelendirme, saç/yüz/kumaşta orta seviye detay, fotogerçekçi değil, dikey 9:16, yazı/altyazı/konuşma balonu yok; sahnelerde loş sinematik ışık, karakter sayfalarında nötr ışık). Sahne promptu karakterleri 2B çizilmiş, mekânı derinlikli 2.5D kompozisyon olarak tarif eder. Varsa `karakterler/stil-sahne.png` karakter referanslarından sonra eklenir; ışık, çizim dili ve katman ayrımı için örnektir. Sahne promptu tek görsel ister ve referans sırasını, karakter görünüşünü ve sahnenin `gorsel` tarifini içerir. Karakter sayfası promptu üç farklı ifade veya duruş adayı ister.
- **Yerleştirme (sahne):** Dosyalar sahnenin ilk boş harflerine (a, b, c) sırayla yerleşir. Üç harf doluysa hata; `--yeniden` ile a'dan başlayarak üzerine yazılır. ffmpeg ile **1080×1920'ye** ölçeklenip ortadan kesilir. Kaynak oranı 9:16'dan çok farklıysa (>%10) uyarı verilir (kesimde çok şey kaybolur).
- **Yerleştirme (karakter):** Tek dosya, PNG'ye çevrilir, kesilmez. Var olan referansın üzerine yalnızca `--yeniden` ile yazılır.
- **Seçim kartı görselleri:** İkilemde `gorsel` tarifi olan her seçenek için `istekler.md`'nin sonuna "## Seçim kartı A/B" bölümü yazılır: referans yalnızca `karakterler/stil.png` (en sonda), prompt **kare 1:1**, tek net nesne/an, karanlık sade arka plan, yazı/harf yok, 3 aday. `--yerlestir secenekA` (veya `secenek_a`) tek dosyayı **1080×1080**'e ölçekleyip ortadan keserek `gorseller/secenek_A.png` yapar; oran kareden >%10 saparsa uyarı. Var olan dosyanın üzerine yalnızca `--yeniden` ile yazılır. Varyant yok: kullanıcı Gemini'de en iyi adayı seçip tek dosya indirir. `montaj.py` kartta bu dosyayı kullanır.
- **Dosya verilmezse:** İndirilenler klasöründeki (`Path.home() / "Downloads"`) en yeni görsel gösterilir ve onay (e/h) istenir.
- **Durum:** Sahnenin ana görseli ve varsa hangi alternatifler hazır, seçim kartı A/B görseli hazır mı, hangi referanslar eksik.

## Proje geneline etkiler
- `CLAUDE.md`: Araçlar, akış (adım 3), klasör yapısı ve yol haritası Gemini API yerine elle üretimi anlatır; Veo çıkar.
- `requirements.txt`'ten `google-genai`, `.env.example`'dan `GEMINI_API_KEY` çıkar; `test_anahtarlar.py` ve `kurulum_kontrol.py` Gemini kontrolünü bırakır.
- `KULLANIM.md` bölüm üretimi listesine görsel adımları eklenir.

## Test
`kod/test_gorsel.py` (düz Python, API ve ağ yok): `hikaye.md`'den tarif okuma, prompt içeriği, referans seçimi ve eksik referans, dosya adları ve boş harf seçimi, `--yeniden`, oran uyarısı hesabı. ffmpeg'li yerleştirme geçici klasörde küçük bir test görseliyle denenir (ffmpeg yoksa atlanır).
Gerçek deneme: `sen` karakter sayfası + Bölüm 1 sahne 1, kullanıcının Gemini uygulamasında ürettiği görsellerle.
