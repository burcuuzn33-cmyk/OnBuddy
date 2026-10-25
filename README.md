# OnBuddy — Yapay Zekâ Destekli İK Asistanı

Wix Studio sitemizdeki ziyaretçilerle yapay zekâ üzerinden Türkçe sohbet eden ve
iletişim bilgisi bırakan adayları kaydeden Flask backend'i. İki arayüz vardır:
karşılama sayfası (sohbet + form) ve adayların listelendiği yönetim paneli.

**Teknolojiler:** Python · Flask · SQLite · Groq (openai/gpt-oss-20b) · Wix Velo · Render

## Mimari

```
run.py                  Giriş noktası (gunicorn run:app)
config.py               Tüm ayarlar (.env'den okunur), geliştirme/üretim sınıfları
app/
├── __init__.py         create_app(): ayarlar → CORS → init_db → bilgi dosyaları → blueprint'ler, /health
├── database.py         SADECE SQL burada (leads, ai_kullanim)
├── routes.py           Sadece yönlendirme ve doğrulama; SQL veya AI kodu içermez
├── services/
│   ├── sohbet_service.py   Sohbet akışı: bütçe → Groq → kullanım kaydı → form yönlendirme etiketi
│   ├── knowledge_service.py  cekirdek.md ve bilgi.md'yi okur (parçalama/arama yok)
│   ├── ai_service.py       SADECE Groq çağrıları burada (yedek model, hata durumları)
│   └── hiz_siniri.py       IP başına sohbet sınırı
└── templates/          index.html (karşılama), dashboard.html (yönetim paneli)
knowledge/              cekirdek.md (rol ve kurallar) + bilgi.md (tek bilgi belgesi)
scripts/degerlendir.py  Gerçek Groq ile 25 soruluk değerlendirme
tests/                  Pytest testleri (Groq taklit edilir)
docs/                   Wix Velo sayfa kodları
```

## Yapay Zekâ

Tek asistan iki tür ziyaretçiye cevap verir; rol seçimi yoktur, model soruyu sorandan anlar:
ürün/şirket soruları → demo formu, iş/pozisyon/başvuru soruları → başvuru formu.

1. Sistem mesajı = `knowledge/cekirdek.md` (rol ve kurallar) + **`knowledge/bilgi.md`'nin tamamı**
   (`<bilgi>` etiketi içinde). Belge parçalanmaz ve aranmaz; her soruda eksiksiz gönderilir.
   `<!-- ... -->` yorum satırları modele gönderilmez.
2. Groq'a gönderilir (`openai/gpt-oss-20b`, temperature 0.3, `reasoning_effort: low`). Kota (429)
   dolarsa veya model hesapta erişilemezse (404) bir kez `openai/gpt-oss-120b` ile denenir.
   Boş veya yarım kalmış cevap gösterilmez. (Bu Groq hesabının Llama modellerine erişimi yoktur.)
3. Form butonu: model, form önerirken cevabın sonuna `[FORM:demo]` veya `[FORM:basvuru]` ekler
   (kural `cekirdek.md`'de). Backend etiketi cevaptan siler ve `yonlendirme` alanına çevirir;
   etiket yoksa `yonlendirme` `null` olur.
4. Token kullanımı `ai_kullanim` tablosuna yazılır (mesaj içeriği yazılmaz). Günlük bütçe
   (`AI_DAILY_TOKEN_BUDGET`) dolunca Groq'a gidilmez.

**Bilgiyi güncellemek:** `knowledge/bilgi.md` dosyasını düzenleyin. Dosya değişince bir sonraki soruda
yeniden okunur; Render'da değişiklik deploy ile gelir. `bilgi.md` veya `cekirdek.md` yoksa ya da boşsa
uygulama açılmaz (soruları sessizce cevapsız bırakmak yerine).

**Bilgi belgesinin boyutu:** Belgenin tamamı her soruda gönderildiği için uzunluğu doğrudan token
tüketir (yaklaşık 3 karakter = 1 token). 15.000 karakteri aşarsa açılışta uyarı yazılır. Groq'un
ücretsiz dakikalık token sınırı ve `AI_DAILY_TOKEN_BUDGET` bu yüzden daha çabuk dolar; belgeyi kısa,
tekrarsız ve olgusal tutun.

> ⚠️ `bilgi.md` içindeki "Kariyer" bölümleri ve açık pozisyon listesi şimdilik **örnek (mock)** içeriktir.
> Gerçek bilgiler gelince güncelleyin.

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
