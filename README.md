# OnBuddy — Yapay Zekâ Destekli İK Asistanı

Wix Studio sitemizdeki ziyaretçilerle yapay zekâ üzerinden Türkçe sohbet eden ve
iletişim bilgisi bırakan adayları kaydeden Flask backend'i. İki arayüz vardır:
karşılama sayfası (sohbet + form) ve adayların listelendiği yönetim paneli.

**Teknolojiler:** Python · Flask · SQLite (FTS5) · Groq (openai/gpt-oss-20b) · Wix Velo · Render

## Mimari

```
run.py                  Giriş noktası (gunicorn run:app)
config.py               Tüm ayarlar (.env'den okunur), geliştirme/üretim sınıfları
app/
├── __init__.py         create_app(): ayarlar → CORS → init_db → bilgi indeksi → blueprint'ler, /health
├── database.py         SADECE SQL burada (leads, pozisyonlar, bilgi_parcalari, ai_kullanim)
├── routes.py           Sadece yönlendirme ve doğrulama; SQL veya AI kodu içermez
├── services/
│   ├── sohbet_service.py   Sohbet akışı: bütçe → bilgi araması → Groq → kullanım kaydı → yönlendirme
│   ├── knowledge_service.py  Dokümanları parçalar, SQLite FTS5'e indeksler, soruya uygun parçaları bulur
│   ├── ai_service.py       SADECE Groq çağrıları burada (yedek model, hata durumları)
│   └── hiz_siniri.py       IP başına sohbet sınırı
└── templates/          index.html (karşılama), dashboard.html (yönetim paneli)
knowledge/              Yapay zekânın bilgi kaynağı (cekirdek.md = sistem mesajı)
scripts/degerlendir.py  Gerçek Groq ile 25 soruluk değerlendirme
tests/                  Pytest testleri (Groq taklit edilir)
docs/                   Wix Velo sayfa kodları
```

## Yapay Zekâ (RAG)

Tek asistan iki tür ziyaretçiye cevap verir; rol seçimi yoktur, model soruyu sorandan anlar:
ürün/şirket soruları → demo formu, iş/pozisyon/başvuru soruları → başvuru formu.

1. Soru ve önceki kullanıcı mesajı, SQLite FTS5 ile `bilgi_parcalari` tablosunda aranır
   (Türkçe ekler için kelimenin ilk 5 harfiyle önek araması). En alakalı 4 parça alınır.
2. Sistem mesajı = `knowledge/cekirdek.md` + bulunan parçalar (`<bilgi>` etiketleri içinde).
   Parça bulunamazsa model bilmediğini söyler.
3. Groq'a gönderilir (`openai/gpt-oss-20b`, temperature 0.3, `reasoning_effort: low`). Kota (429)
   dolarsa veya model hesapta erişilemezse (404) bir kez `openai/gpt-oss-120b` ile denenir.
   Boş veya yarım kalmış cevap gösterilmez. (Bu Groq hesabının Llama modellerine erişimi yoktur.)
4. Token kullanımı `ai_kullanim` tablosuna yazılır (mesaj içeriği yazılmaz). Günlük bütçe
   (`AI_DAILY_TOKEN_BUDGET`) dolunca Groq'a gidilmez.

**Bilgi kaynağını güncellemek:** `knowledge/` altındaki `.md` dosyalarını düzenleyin; uygulama açılırken
değişen dosyalar otomatik yeniden indekslenir. Her `## ` başlığı bir arama parçasıdır.
Açık pozisyonlar `pozisyonlar` tablosundan gelir; pozisyon değiştikten sonra
`bilgi_servisi.pozisyonlari_indeksle()` çağrılmalıdır.

> ⚠️ `knowledge/kariyer.md` ve `knowledge/ornek_pozisyonlar.json` şimdilik **örnek (mock)** içeriktir.
> Gerçek bilgiler gelince güncelleyin ve `ORNEK_POZISYONLARI_YUKLE=0` yapın.

## Testler

```bash
pip install -r requirements-dev.txt
python -m pytest -q                 # Groq'a gitmez
python -m scripts.degerlendir       # gerçek Groq ile; .env'de GROQ_API_KEY gerekir
```

## Kurulum

```bash
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env       # macOS/Linux: cp .env.example .env  → GROQ_API_KEY'i doldurun
python run.py
```

- Karşılama sayfası: http://localhost:5000/
- Yönetim paneli: http://localhost:5000/dashboard
- Sağlık kontrolü: http://localhost:5000/health

## API

| Metot | Yol | Gönderilen | Dönen |
|---|---|---|---|
| POST | `/api/sohbet` | `mesaj` (≤1000 karakter), `gecmis` | `basari`, `cevap`, `yonlendirme` (`demo_formu` / `basvuru_formu` / `null`) |
| POST | `/api/leads` | `isim`, `telefon`, `eposta?`, `pozisyon?`, `mesaj?` | `basari`, `mesaj` (201) |
| GET | `/api/leads` | — | `basari`, `toplam`, `leadler` |
| GET | `/health` | — | `durum: "aktif"` |

Hatalarda `{"basari": false, "hata": "..."}` döner: eksik/hatalı veri 400, istek çok büyük 413,
çok fazla istek veya Groq kotası dolu 429 (`Retry-After` başlığıyla), yapay zekâ hatası 503.

## Güvenlik

- SQL sorgularında `?` yer tutucusu kullanılır (SQL Injection koruması).
- API anahtarları `.env` içindedir ve `.gitignore` ile GitHub'dan uzak tutulur.
- CORS: canlıda `CORS_ORIGINS` yalnızca Wix sitemizin adresine ayarlanır.

## Wix Bağlantısı

`docs/wix_karsilama.js` ve `docs/wix_panel.js` dosyalarını ilgili Wix sayfalarının
Velo koduna yapıştırın, dosyadaki bileşen ID'lerini verin ve `API` adresini Render
adresinizle değiştirin.

## Yayınlama (Render)

- Build: `pip install -r requirements.txt`
- Start: `gunicorn run:app`
- Environment: `FLASK_ENV=production`, `GROQ_API_KEY`, `SECRET_KEY`, `CORS_ORIGINS`
  (diğer ayarlar ve varsayılanları için `.env.example`)
- ⚠️ Render'ın ücretsiz planında disk kalıcı değildir; `onbuddy.db` yeniden başlatmada silinir.
  Kalıcı veri için ücretli planda persistent disk ekleyip `DATABASE_URL`'i o diske yönlendirin.
