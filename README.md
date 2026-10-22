# OnBuddy — Yapay Zekâ Destekli İK Asistanı

Wix Studio sitemizdeki ziyaretçilerle yapay zekâ üzerinden Türkçe sohbet eden ve
iletişim bilgisi bırakan adayları kaydeden Flask backend'i. İki arayüz vardır:
karşılama sayfası (sohbet + form) ve adayların listelendiği yönetim paneli.

**Teknolojiler:** Python · Flask · SQLite · Groq (Llama 3.1) · Wix Velo · Render

## Mimari

```
run.py                  Giriş noktası (gunicorn run:app)
config.py               Tüm ayarlar (.env'den okunur), geliştirme/üretim sınıfları
app/
├── __init__.py         create_app(): ayarlar → CORS → init_db → blueprint'ler, /health
├── database.py         SADECE SQL burada (get_db, init_db, lead_ekle, tum_leadler)
├── routes.py           Sadece yönlendirme; SQL veya AI kodu içermez
├── services/
│   └── ai_service.py   SADECE yapay zekâ çağrıları burada (AIService.yanit_uret)
└── templates/          index.html (karşılama), dashboard.html (yönetim paneli)
docs/                   Wix Velo sayfa kodları
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
| POST | `/api/sohbet` | `mesaj`, `gecmis` | `basari`, `cevap` |
| POST | `/api/leads` | `isim`, `telefon`, `eposta?`, `pozisyon?`, `mesaj?` | `basari`, `mesaj` (201) |
| GET | `/api/leads` | — | `basari`, `toplam`, `leadler` |
| GET | `/health` | — | `durum: "aktif"` |

Hatalarda `{"basari": false, "hata": "..."}` döner: eksik veri 400, yapay zekâ hatası 503.

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
- Environment: `FLASK_ENV=production`, `GROQ_API_KEY`, `SECRET_KEY`, `CORS_ORIGINS`, `BUSINESS_CONTEXT`
