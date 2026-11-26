# Kullanım rehberi (kopya kâğıdı)

## Altın kural
**Karar alındıysa dosyaya yazılır.** Sohbetler geçicidir, dosyalar kalıcıdır.

| Ne oldu? | Nereye yazılır? |
|---|---|
| Hikâye kararı (tür, karakter, olay örgüsü) | `hikaye.md` |
| Yol haritasında bir adım bitti | `CLAUDE.md` |
| Bölüm yayınlandı, kazanan seçim belli oldu | `durum.json` |
| Aklına bir fikir geldi | `fikirler.md` |

## Nerede ne yapılır?

| Yer | Ne için | Ne için DEĞİL |
|---|---|---|
| **Claude Code → Hikâye · Geliştirme** | Kod yazmak. Yol haritası adımı başına 1 oturum. | Bölüm üretmek |
| **Claude Code → Hikâye · Üretim** | Bölüm üretmek. Bölüm başına 1 oturum. | Kod değiştirmek (küçük düzeltme hariç) |
| **claude.ai → "Hikâye Projesi"** | Telefonda ve yolda beyin fırtınası | Karar saklamak (kararı buraya taşı) |
| **VS Code** | Senaryoyu (`senaryo.json`) okumak ve düzenlemek | — |
| **Terminal** | `python kod/...` komutları | — |
| **Apple Notlar** | Anlık fikir. Haftada bir `fikirler.md`'ye aktar. | — |

## Yeni oturum açarken
1. Klasör: **`hikaye is`** seçili olsun (yoksa Claude projeyi tanımaz).
2. Başlık ver: `Adım 2: gorsel.py` veya `Bölüm 03`.
3. Doğru bölüme sürükle (Geliştirme / Üretim).
4. İlk mesajı net yaz: "Adım 2'ye başla" / "B kazandı, Bölüm 3'ün senaryosunu yaz".
5. İş bitince: dosyalar güncellendi mi? commit atıldı mı? → oturumu **arşivle**.

Konu değişirse aynı sohbette devam etme, yeni oturum aç.

## Geliştirme adımı (Faz A)
- [ ] Yeni oturum: "Adım N'e başla"
- [ ] Birlikte tasarla, kodu yaz
- [ ] Gerçek veriyle tek başına test et
- [ ] `CLAUDE.md`'de adımı işaretle
- [ ] Commit
- [ ] Oturumu arşivle

## Bölüm üretimi (Faz B, ~20–40 dk)
- [ ] Oylama bitti → yeni oturum "Bölüm N"
- [ ] "X kazandı, durum.json'a işle ve Bölüm N'in senaryosunu yaz"
- [ ] Senaryoyu VS Code'da oku ve düzelt
- [ ] `python kod/yeni_bolum.py N` → görsel seç, sesleri dinle
- [ ] Videoyu telefonda izle
- [ ] Yükle: **AI etiketi** + anket
- [ ] `bolumler/` klasörünü yedekle (iCloud / harici disk)
- [ ] Oturumu arşivle

## Sık kullanılan komutlar
```bash
cd "/Users/emre/Desktop/hikaye is"
.venv/bin/python kod/test_anahtarlar.py   # anahtarlar + kalan ElevenLabs karakteri
git status                                 # neler değişti?
```

## Limitler
- **Pro:** Claude Code ve claude.ai aynı limiti paylaşır (yaklaşık 5 saatte bir yenilenir). Kodlama ile üretimi aynı pencereye yığma.
- **ElevenLabs (ücretsiz):** ayda 10.000 karakter ≈ 5–8 bölüm. Ay ortasında kontrol et.
- **Gizli:** `.env` git'e girmez, anahtarları kimseyle paylaşma.
