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
| **Claude Code → Hikâye · Planlama** | Hikâyenin genel hatları: dünya, karakterler, olay örgüsü, dallanmalar → `hikaye.md`. Başta yoğun, sonra ara ara. | Kod yazmak |
| **Claude Code → Hikâye · Kod** | Pipeline modüllerini yazmak. Yol haritası adımı başına 1 oturum. | Hikâye kararı vermek |
| **Claude Code → Hikâye · Bölümler** | Bölüm üretmek. Bölüm başına 1 oturum. | Kod değiştirmek (küçük düzeltme hariç) |
| **claude.ai → "Hikâye Projesi"** | Telefonda ve yolda beyin fırtınası | Karar saklamak (kararı buraya taşı) |
| **VS Code** | Senaryoyu (`senaryo.json`) okumak ve düzenlemek | — |
| **Terminal** | `python kod/...` komutları | — |
| **Apple Notlar** | Anlık fikir. Haftada bir `fikirler.md`'ye aktar. | — |

## Yeni oturum açarken
1. Klasör: **`hikaye is`** seçili olsun (yoksa Claude projeyi tanımaz).
2. Başlık ver: `Hikâye planı`, `Adım 2: gorsel.py` veya `Bölüm 03`.
3. Doğru bölüme sürükle (Planlama / Kod / Bölümler).
4. İlk mesajı net yaz: "Hikâyeyi planlayalım" / "Adım 2'ye başla" / "B kazandı, Bölüm 3'ün senaryosunu yaz".
5. İş bitince: dosyalar güncellendi mi? commit atıldı mı? → oturumu **arşivle**.

Konu değişirse aynı sohbette devam etme, yeni oturum aç.

## Hikâye planlama
- [ ] Yeni oturum (Planlama): "Hikâyeyi planlayalım"
- [ ] Tür → dünya → karakterler → ana olay örgüsü → dallanma noktaları
- [ ] Her karar `hikaye.md`'ye yazıldı mı?
- [ ] Commit, oturumu arşivle
- Sonra: hafta sonu `fikirler.md` gözden geçirmesi de burada yapılır.

## Kod adımı (Faz A)
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
- [ ] Karakter referansı eksikse: `python kod/gorsel.py bolumler/bolum_NN/senaryo.json --karakter <kimlik>` → Gemini uygulamasında üret → `--yerlestir <kimlik>`
- [ ] `python kod/gorsel.py bolumler/bolum_NN/senaryo.json` → `gorseller/istekler.md`'deki her sahne için Gemini uygulamasında 3 görsel üret, indir → `--yerlestir <sahne no>` (dosya verilmezse İndirilenler'deki en yenileri alır)
- [ ] `--durum` ile eksik sahne kalmadığını kontrol et
- [ ] `python kod/yeni_bolum.py N` → görsel seç, sesleri dinle
- [ ] Videoyu telefonda izle
- [ ] Yükle: **AI etiketi** + anket
- [ ] `bolumler/` klasörünü yedekle (iCloud / harici disk)
- [ ] Oturumu arşivle

## Sık kullanılan komutlar
```bash
cd "/Users/emre/Desktop/hikaye is"
.venv/bin/python kod/kurulum_kontrol.py   # bu cihazın kurulumu eksiksiz mi?
.venv/bin/python kod/test_anahtarlar.py   # anahtarlar + kalan ElevenLabs karakteri
git status                                 # neler değişti?
```

## Cihaz değiştirirken
- **Kalkmadan önce:** commit + push (Claude'a "gönder" de).
- **Oturunca:** `git pull`.
- İki cihazda aynı anda değişiklik yapma.
- `.env` git'te yoktur: anahtarlar şifre yöneticisinde (Apple Şifreler) dursun.
- `karakterler/stil.png` (görsel stil örneği) git'te yoktur: `hikaye-medya` yedeğiyle birlikte diğer cihaza elle kopyala; yoksa `gorsel.py` istekleri stil örneği olmadan yazar.
- Üretilen medya (`bolumler/`) git'te yoktur: iCloud Drive'daki `hikaye-medya` klasörüne yedekle. Proje klasörünün tamamını iCloud'a koyma.

## Windows'ta ilk kurulum (bir kez)
PowerShell'de, sırayla:
```powershell
winget install Git.Git GitHub.cli astral-sh.uv Gyan.FFmpeg Microsoft.VisualStudioCode
```
Terminali kapatıp aç (PATH yenilensin), sonra:
```powershell
gh auth login
gh repo clone EmreUnver-Seng/hikaye "$HOME\Desktop\hikaye"
cd "$HOME\Desktop\hikaye"
uv venv --python 3.12
uv pip install -r requirements.txt
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
```
- `.env` dosyasını oluştur: `.env.example`'ı kopyala, anahtarları şifre yöneticisinden yapıştır.
- Git kimliği (depo klasöründe): `git config user.name "Emre"` ve `git config user.email "255063380+EmreUnver-Seng@users.noreply.github.com"`
- Kurulum kontrolü: `.venv\Scripts\python kod\kurulum_kontrol.py` → çıktıyı Claude'a yapıştır.
- Anahtar kontrolü: `.venv\Scripts\python kod\test_anahtarlar.py`
- Claude masaüstü uygulamasını kur, Code sekmesinde bu klasörü aç ve Claude'a **"oturum düzenini kur"** de (ayrıntı aşağıda).

## Oturum düzeni (yeni cihazda Claude kurar)
Kullanıcı **"oturum düzenini kur"** dediğinde Claude, Claude masaüstü uygulamasının Code sekmesinde şunları yapar:

1. Kenar çubuğundaki bölümleri listeler. Aşağıdakilerden eksik olanları, **adı birebir aynı** olacak şekilde ve bu sırayla oluşturur (var olanı tekrar oluşturmaz):
   | Sıra | Bölüm adı | İçine giren oturumlar |
   |---|---|---|
   | 1 | `Hikâye · Planlama` | Hikâye kararları → `hikaye.md` |
   | 2 | `Hikâye · Kod` | Yol haritası adımları (pipeline modülleri) |
   | 3 | `Hikâye · Bölümler` | Bölüm başına üretim oturumu |
2. İçinde bulunduğu oturumu `Hikâye · Kod` bölümüne taşır ve adını `Kurulum: <cihaz adı>` yapar (ör. `Kurulum: Windows`).
3. Bu projeye ait olmayan oturumlara ve uygulama ayarlarına **dokunmaz**.
4. `kod/kurulum_kontrol.py`'yi çalıştırır, sorun varsa kullanıcıya çözümünü söyler.
5. Yaptıklarını kısaca raporlar ve sıradaki adımı (`CLAUDE.md` → yol haritası) söyler.

Oturum adları için kalıp: `Hikâye planı`, `Adım N: <modül>`, `Bölüm NN`.

**Mac ↔ Windows farkı:** Python yolu Mac'te `.venv/bin/python`, Windows'ta `.venv\Scripts\python`.

## Limitler
- **Pro:** Claude Code ve claude.ai aynı limiti paylaşır (yaklaşık 5 saatte bir yenilenir). Kodlama ile üretimi aynı pencereye yığma.
- **ElevenLabs (ücretsiz):** ayda 10.000 karakter ≈ 5–8 bölüm. Ay ortasında kontrol et.
- **Gizli:** `.env` git'e girmez, anahtarları kimseyle paylaşma.
