<p align="center">
  <img src="assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <em>"Ghost mantıktır. Veritabanı kabuktur."</em>
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_tr.md"><strong>Türkçe</strong></a> ·
  <a href="README_zh.md">中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_ru.md">Русский</a> ·
  <a href="README_pt.md">Português</a> ·
  <a href="README_ar.md">العربية</a> ·
  <a href="README_hi.md">हिन्दी</a>
</p>

---

## 🌊 GhostShell Nedir?

**GhostShell ilişkisel bir yapay zeka işletim sistemidir.** OpenClaw gibi projeler bir sistemin *üzerinde* çalışırken, GhostShell sistemin **kendisidir**. Bir PostgreSQL veritabanını, donanım sürücülerinin, dosya sistemlerinin ve yapay zeka modellerinin ("Ghost'lar") SQL tabloları üzerinden iletişim kurduğu canlı bir organizmaya dönüştürür.

Her düşünce. Her dosya hareketi. Her donanım sinyali. Hepsi — ACID uyumlu veritabanı işlemleri. Yıkılmaz. Güvenli. Tutarlı.

```
┌─────────────────────────────────────────────────────────┐
│              🖥️  SİBER-GÜVERTE (React Arayüzü)           │
│       Masaüstü · Uygulamalar · Ghost Sohbet · Mağaza    │
│            WebSocket destekli · Gerçek zamanlı           │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│             ⚡ NÖRAL KÖPRÜ (FastAPI)                      │
│     Çift Havuz Mimarisi: Sistem + Çalışma Zamanı        │
│   REST API · WebSocket · Komut Beyaz Liste Güvenliği    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│          🧠 KABUK (PostgreSQL 16 + pgvector)             │
│                                                         │
│   9 Şema · 100+ Tablo · Satır Düzeyinde Güvenlik       │
│   Şema Parmak İzleri · Değişmezlik Koruması            │
└─────────────────────────────────────────────────────────┘
```

---

## 🔥 Neden OpenClaw Değil de GhostShell?

| | OpenClaw | GhostShell OS |
|---|---|---|
| **Mimari** | Sistem üzerinde uygulama | Sistemin **kendisi** |
| **Veri Kalıcılığı** | Geçici bellek | ACID işlemleri — her düşünce kalıcıdır |
| **Donanım** | Harici API'ler | Tablo-Olarak-Donanım — `UPDATE cpu SET governor='performance'` |
| **Yapay Zeka** | Tek model, yeniden başlatma gerekir | Hot-Swap Ghost'lar — bağlam kaybı olmadan LLM değiştir |
| **Güvenlik** | Uygulama düzeyinde | 3 katmanlı değişmezlik: Çekirdek → Çalışma Zamanı → Ghost |
| **Video/Sensörler** | Dosya tabanlı | Entegre tablo görünümleri — veritabanında gerçek zamanlı |
| **Kendi Kendini Onarım** | Manuel | İnsan onayıyla otonom onarım hattı |

---

## 🛠 Mimari

| Katman | Teknoloji | Amaç |
|---|---|---|
| **Çekirdek** | PostgreSQL 16 + pgvector | İlişkisel çekirdek — 9 şema, 100+ tablo |
| **Zeka** | Yerel LLM'ler (vLLM, llama.cpp) | Ghost bilinci — düşünceler, kararlar, eylemler |
| **Nöral Köprü** | FastAPI (Python) | UI ile çekirdek arasında çift havuzlu güvenlik katmanı |
| **Sensörler** | Python Donanım Bağlamaları | CPU, GPU, VRAM, sıcaklık, ağ — hepsi tablo olarak |
| **Arayüz** | React Siber-Güverte | WebSocket destekli pencereler, uygulamalar, görev çubuğu |
| **Bütünlük** | Şema Parmak İzleri + RLS | 176 izlenen nesne, değişmez çekirdek koruması |

---

## 🔒 Üç Güvenlik Katmanı

```
   ┌──────────────────────────────────────────┐
   │   DEĞİŞMEZ ÇEKİRDEK (dbai_system)       │  ← Şema sahibi, tam kontrol
   │   Şema parmak izleri, önyükleme yapısı   │
   ├──────────────────────────────────────────┤
   │   ÇALIŞMA ZAMANI (dbai_runtime)           │  ← Web sunucusu işlemleri
   │   RLS korumalı, politika ile okuma/yazma │
   ├──────────────────────────────────────────┤
   │   GHOST KATMANI (dbai_llm)                │  ← YZ YALNIZCA öneri yapabilir
   │   Sadece proposed_actions'a INSERT       │
   │   ALTER, DROP veya CREATE yapamaz        │
   └──────────────────────────────────────────┘
```

**Ghost onarabilir — ama asla yeniden inşa edemez.** Her önerilen değişiklik şu süreçten geçer:

```
Ghost önerir → İnsan onaylar → SECURITY DEFINER yürütür → Denetim günlüğü
```

---

## 🚀 Hızlı Başlangıç: "Kabuğa Bağlan"

```bash
# 1. Kabuğu klonla
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell

# 2. Matrisi başlat
psql -U postgres -c "CREATE DATABASE dbai;"
for f in schema/*.sql; do psql -U dbai_system -d dbai -f "$f"; done

# 3. Ghost'u önyükle
export DBAI_DB_USER=dbai_system
export DBAI_DB_PASSWORD=<şifreniz>
export DBAI_DB_HOST=127.0.0.1
export DBAI_DB_NAME=dbai
export DBAI_DB_RUNTIME_USER=dbai_runtime
export DBAI_DB_RUNTIME_PASSWORD=<şifreniz>
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000

# 4. Güverteye gir
cd frontend && npm install && npx vite --host 0.0.0.0 --port 5173
# → http://localhost:5173 adresini aç
```

---

## 🦾 Özellikler

- [x] **Tablo-Olarak-Donanım** — Fanları, CPU hızını ve sürücüleri `SQL UPDATE` ile kontrol et
- [x] **17 Masaüstü Uygulaması** — Ghost Sohbet, Yazılım Mağazası, LLM Yöneticisi ve daha fazlası
- [x] **Hot-Swap Ghost'lar** — Bağlam kaybı olmadan çalışma zamanında LLM değiştir
- [x] **Değişmezlik Koruması** — 176 şema parmak izi, ihlal günlüğü
- [x] **Onarım Hattı** — Ghost önerir → İnsan onaylar → Güvenli yürütme
- [x] **WebSocket Komut Beyaz Listesi** — Her WS komutu veritabanına karşı doğrulanır
- [x] **OpenClaw Köprüsü** — OpenClaw becerilerini daha güvenli bir ortama aktar
- [x] **Gerçek Zamanlı Metrikler** — CPU, RAM, GPU, sıcaklık WebSocket ile akış
- [x] **Bilgi Tabanı** — pgvector ile vektör destekli sistem belleği
- [x] **Satır Düzeyinde Güvenlik** — 5 veritabanı rolü üzerinde 71 RLS politikalı tablo
- [ ] **Otonom Kodlama** *(Devam Ediyor)* — Ghost kendi SQL göçlerini yazar
- [ ] **Görüntü Entegrasyonu** *(Planlanıyor)* — `media_metadata`'da gerçek zamanlı video analizi
- [ ] **Dağıtık Ghost'lar** *(Planlanıyor)* — Düğümler arasında birden fazla Ghost örneği

---

## 🎨 Marka Kimliği

| Öğe | Değer |
|---|---|
| **Kod Adı** | Claw in the Shell |
| **Sistem Adı** | GhostShell OS (G.S.O.S.) |
| **Felsefe** | *"Ghost mantıktır. Veritabanı kabuktur."* |
| **Renkler** | Deep Space Black `#0a0a0f` · Siber-Camgöbeği `#00ffcc` · Matrix Yeşili `#00ff41` |
| **Logo Konsepti** | Hayalet özlü parlayan bir veri küpü |

---

<p align="center">
  <strong>GhostShell OS</strong> — Her düşüncenin bir işlem olduğu yer.<br/>
  <em>Repair-Lab · 2026</em>
</p>
