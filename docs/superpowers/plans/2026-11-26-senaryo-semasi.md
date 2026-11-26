# Senaryo şeması ve doğrulayıcı — Uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `senaryo.json` dosyasını doğrulayan, tek başına çalışan `kod/senaryo.py` ve gerçek bir Bölüm 1 senaryosu.

**Architecture:** Tek modül: saf bir `dogrula(veri, klasor_adi=None) -> (hatalar, uyarilar)` fonksiyonu, dosyayı okuyan `senaryo_yukle(yol)` ve bir CLI `main()`. Testler düz Python betiği; geçerli bir sözlüğü bozup her hatanın yakalandığını kontrol eder.

**Tech Stack:** Python 3.12 standart kütüphane (`json`, `pathlib`, `sys`). Ek bağımlılık yok.

**Spec:** `docs/superpowers/specs/2026-11-26-senaryo-semasi-design.md`

## Global Constraints
- Yollar `pathlib.Path`; dosyalar `encoding="utf-8"`; `shell=True` yok.
- Tüm kullanıcıya dönük mesajlar Türkçe.
- Karakter kimlikleri: `sen, fatma, riza, kerem, murat, ayla`; konuşan ayrıca `anlatici`.
- Sahne sayısı 8–12; süre 45–90 sn (2,5 kelime/sn); "sen" cümlesi > 3 → uyarı; cümle > 25 kelime → uyarı.
- Windows konsolunda Türkçe karakter bozulmamalı: `sys.stdout.reconfigure(encoding="utf-8")`.

## Review Focus
- JSON sözdizim hatası (eksik virgül) → satır/sütunlu Türkçe mesaj, Python traceback değil.
- Dosya yok / klasör yolu verilmiş → anlaşılır mesaj, çıkış kodu 1.
- Tür hatası alt alanları çökertmemeli (ör. `sahneler` sözlükse veya `cumleler` stringse) → tek hata, devam.
- `bolum: true` (bool, int'in alt sınıfı) → tür hatası.
- Hatalar konumuyla: `sahneler[2].cumleler[0].konusan`.

---

### Task 1: `kod/senaryo.py` + testler

**Files:** Create `kod/senaryo.py`, `kod/test_senaryo.py`

**Interfaces:**
- Produces: `dogrula(veri: object, klasor_adi: str | None = None) -> tuple[list[str], list[str]]`; `senaryo_yukle(yol: Path) -> dict` (geçersizse `SenaryoHatasi(Exception)` fırlatır, `.hatalar` listesiyle); `KARAKTERLER: tuple[str, ...]`; `main(argv) -> int`.

- [ ] Test yaz: `gecerli_ornek()` 8 sahneli sözlük → hata yok. Her bozulma için ayrı test: eksik `baslik`, bilinmeyen alan, `bolum` 9 / `true`, 7 ve 13 sahne, `no` sırası bozuk, bilinmeyen karakter, tekrarlı karakter, konuşan sahnede yok, boş `metin`, boş `cumleler`, `cumleler` string, bölüm 3'te `secenekler` eksik / `C` var, bölüm 8'de `secenekler` var, klasör `bolum_02` ama `bolum: 1`. Uyarılar: 4 "sen" cümlesi, 26 kelimelik cümle, kısa süre. CLI: bozuk JSON dosyası → çıkış 1 ve mesajda "satır"; olmayan dosya → çıkış 1.
- [ ] Çalıştır: `.venv\Scripts\python kod\test_senaryo.py` → içe aktarma hatasıyla düşer.
- [ ] `senaryo.py`'yi yaz (spec'teki kontroller).
- [ ] Çalıştır → `Tüm testler geçti`.

### Task 2: Bölüm 1 senaryosu

**Files:** Create `bolumler/bolum_01/senaryo.json`

- [ ] `hikaye.md` Bölüm 1 rotasına göre 8–12 sahne, ikilem B1 (A: zarfı aç / B: açma). İlk sahne şok/soru ile açılır.
- [ ] `.venv\Scripts\python kod\senaryo.py bolumler\bolum_01\senaryo.json` → geçerli, uyarı yok, süre 45–90 sn.

### Task 3: Kapanış
- [ ] `CLAUDE.md`'de adım 1'i işaretle, "SIRADAKİ ADIM" işaretini adım 2'ye taşı; Windows test komutu ekle.
- [ ] Kullanıcı onayından sonra commit (spec, plan, kod, senaryo, CLAUDE.md).
