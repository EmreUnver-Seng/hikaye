# Senaryo şeması ve `senaryo.py` (Yol haritası adım 1)

## Amaç
Her bölümün senaryosu `bolumler/bolum_NN/senaryo.json` dosyasında durur. Bu dosya sonraki modüllerin ortak girdisidir:
- `gorsel.py`: sahnenin görsel tarifi + sahnedeki karakterlerin referans görselleri,
- `ses.py`: cümle cümle seslendirme; her cümlenin **konuşanı** ayrı bir ElevenLabs sesiyle,
- `montaj.py`: sahne sırası, altyazı ve sondaki A/B seçenek kartı.

`senaryo.py` dosyayı doğrular ve sorunları okunur Türkçe mesajlarla listeler. Senaryo Claude Code'da elle yazıldığı için hatayı üretimden (API harcamadan) önce yakalamak asıl hedef.

## Kararlar (kullanıcıyla)
- **Konuşanlar:** Anlatıcı hikâye akışını anlatır ve izleyiciyle "sen" diye konuşur. Karakter replikleri her karakterin **kendi sesiyle** duyulur.
- **"Sen" nadiren konuşur:** Kısa cümleler ("Kimse yok mu?") veya bir önceki bölümde seçilen sözü söylediği açılış sahnesi gibi durumlarda. İzin verilir; bölümde 3'ten fazla "sen" cümlesi olursa **uyarı** verilir (hata değil).
- **Ses kimlikleri senaryoda yok:** Karakter → ElevenLabs ses eşlemesi adım 3'te ayrı dosyada tutulacak (ör. `karakterler/sesler.json`).
- **Doğrulama elle yazılır** (standart kütüphane, ek bağımlılık yok). Seçilmeyen yollar: `jsonschema` / `pydantic` — hata mesajları İngilizce, alanlar arası kontroller yine elle yazılmalı.

## Şema
```json
{
  "bolum": 1,
  "baslik": "Kalkış",
  "sahneler": [
    {
      "no": 1,
      "mekan": "otobus",
      "gorsel": "İngilizce veya Türkçe görsel tarifi",
      "karakterler": ["sen", "nadide"],
      "cumleler": [
        { "konusan": "anlatici", "metin": "Saat 23:30. Otobüse biniyorsun." },
        { "konusan": "nadide", "metin": "Son durağa kadar açma, evladım." }
      ]
    }
  ],
  "ikilem": {
    "soru": "Zarfı şimdi açacak mısın?",
    "secenekler": { "A": "Zarfı aç", "B": "Söz verdin, açma" }
  }
}
```
Mekân (`mekan`, isteğe bağlı ama önerilir): `otobus, tesis, istasyon, dis` (`dis` = otogar, yol gibi gece dış mekânı). Tarifi `hikaye.md`'deki "Mekânlar" ve "Renk paleti" bölümlerinden alınır ve `gorsel.py` tarafından prompt'a eklenir; böylece koltuk rengi gibi ayrıntılar sahne tarifinde yazmasa da tutarlı kalır.

Seçenekler iki biçimde yazılabilir (geriye uyumlu): düz yazı (`"A": "Zarfı aç"`) ya da seçim kartında görsel isteniyorsa nesne:
```json
"secenekler": {
  "A": { "metin": "Zarfı aç", "gorsel": "Açılmış kahverengi zarf, içinden katlanmış kâğıt görünüyor." },
  "B": "Söz verdin, açma"
}
```
Nesnede `metin` zorunlu, `gorsel` isteğe bağlı; başka alan hata. `gorsel` tarifinden `gorsel.py` kare (1:1) bir Gemini isteği üretir; görsel `gorseller/secenek_A.png` olarak yerleşir ve `montaj.py` seçim kartında kullanır. Diğer modüller `secenek_metni(deger)` / `secenek_gorseli(deger)` yardımcılarıyla okur.

Karakter kimlikleri: `sen, nadide, riza, kerem, murat, ayla` (referans: `karakterler/<kimlik>.png`). Konuşan ayrıca `anlatici` olabilir.

## Kontroller
**Hata** (dosya geçersiz):
- JSON okunamıyor (satır/sütun ile), kök nesne değil, zorunlu alan eksik, tür yanlış, bilinmeyen alan (yazım hatalarını yakalamak için).
- `bolum` 1–8 arası tam sayı; klasör adı `bolum_NN` ise numarayla eşleşmeli.
- `baslik`, `gorsel`, `metin`, `soru`, seçenek metinleri ve seçenek görsel tarifleri boş olamaz; seçenek yazı ya da `{metin, gorsel}` nesnesi olmalı.
- 8–12 sahne; `no` 1'den başlayıp sırayla artar.
- `karakterler` bilinen kimliklerden oluşur, tekrar yok (boş liste olabilir: manzara sahnesi).
- `cumleler` en az 1 eleman; `konusan` `anlatici` ya da sahnenin `karakterler` listesindeki biri.
- `ikilem.soru` zorunlu; bölüm 1–7'de `secenekler` tam olarak `A` ve `B`; bölüm 8'de `secenekler` yok.

**Uyarı** (dosya geçerli, gözden geçir):
- Tahmini süre (kelime sayısı / ~2,5 kelime/sn) 45–90 sn dışında.
- 3'ten fazla "sen" cümlesi.
- Sahnede `mekan` yazılmamış (bilinmeyen değer ise **hata**).
- Tek cümle 25 kelimeden uzun (altyazıya sığmaz).

## Kullanım
`python kod/senaryo.py bolumler/bolum_01/senaryo.json` → hata yoksa özet (sahne sayısı, tahmini süre, konuşanlar) ve çıkış kodu 0; hata varsa tüm hatalar `sahne 4, cümle 2, konusan: ...` gibi 1'den sayılan konum bilgisiyle, çıkış kodu 1. Diğer modüller `senaryo_yukle(yol)` fonksiyonunu çağırır (geçersizse hata fırlatır).

## Test
Geçerli örnek: `hikaye.md`'ye uygun gerçek Bölüm 1 senaryosu. Bozuk örnekler: `kod/test_senaryo.py` (pytest değil, düz Python) bozuk kopyalar üretip her hatanın yakalandığını kontrol eder.
