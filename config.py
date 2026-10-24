import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasındaki değerleri ortam değişkenlerine yükler.
# En başta çağrılmalı; yoksa aşağıdaki os.environ.get(...) satırları .env'i göremez.
load_dotenv()

PROJE_KLASORU = Path(__file__).resolve().parent


def _origin_listesi(deger):
    """CORS için 'https://a.com, https://b.com' metnini listeye çevirir. '*' herkese izin verir."""
    deger = (deger or "*").strip()
    if deger == "*":
        return "*"
    return [o.strip() for o in deger.split(",") if o.strip()]


def _sayi(ad, varsayilan, tip=int):
    """Ortam değişkenini sayıya çevirir; boş veya hatalıysa varsayılanı kullanır."""
    try:
        return tip(os.environ.get(ad, varsayilan))
    except (TypeError, ValueError):
        return varsayilan


class Config:
    """Tüm ayarlar tek yerde. Her değer önce .env'den okunur, yoksa güvenli varsayılan kullanılır."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "gelistirme-icin-gizli-anahtar")
    DATABASE_URL = os.environ.get("DATABASE_URL", "onbuddy.db")

    # Yapay zekâ: Groq. Ana model kota (429) verirse bir kez yedek modelle denenir.
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
    AI_TEMPERATURE = _sayi("AI_TEMPERATURE", 0.3, float)
    AI_MAX_TOKENS = _sayi("AI_MAX_TOKENS", 400)
    AI_TIMEOUT = _sayi("AI_TIMEOUT", 15)            # saniye
    AI_HISTORY_MAX_MESSAGES = _sayi("AI_HISTORY_MAX_MESSAGES", 6)
    AI_HISTORY_MAX_CHARS = _sayi("AI_HISTORY_MAX_CHARS", 2400)
    # Günlük toplam token sınırı; aşılırsa Groq'a gidilmez (kota birinin yüzünden bitmesin)
    AI_DAILY_TOKEN_BUDGET = _sayi("AI_DAILY_TOKEN_BUDGET", 300000)

    # RAG: bilgi dokümanları ve SQLite FTS5 araması
    KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", str(PROJE_KLASORU / "knowledge"))
    RAG_TOP_K = _sayi("RAG_TOP_K", 4)
    RAG_MAX_CHUNK_CHARS = _sayi("RAG_MAX_CHUNK_CHARS", 800)
    # Pozisyon tablosu boşsa knowledge/ornek_pozisyonlar.json ile doldurulur (şimdilik mock veri)
    ORNEK_POZISYONLARI_YUKLE = os.environ.get("ORNEK_POZISYONLARI_YUKLE", "1") == "1"

    # Kötüye kullanım koruması: IP başına sohbet sınırı ve istek gövdesi boyutu
    CHAT_RATE_LIMIT_REQUESTS = _sayi("CHAT_RATE_LIMIT_REQUESTS", 10)
    CHAT_RATE_LIMIT_WINDOW_SECONDS = _sayi("CHAT_RATE_LIMIT_WINDOW_SECONDS", 60)
    CHAT_MESSAGE_MAX_CHARS = _sayi("CHAT_MESSAGE_MAX_CHARS", 1000)
    MAX_CONTENT_LENGTH = _sayi("MAX_CONTENT_LENGTH", 65536)  # byte

    # Hangi sitelerin (ör. Wix sitemiz) API'ye istek atabileceği.
    # Geliştirmede "*", canlıda kendi Wix adresimiz: https://kullanici.wixstudio.com
    # (Eski isim CORS_ALLOWED_ORIGINS da desteklenir.)
    CORS_ORIGINS = _origin_listesi(
        os.environ.get("CORS_ORIGINS") or os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    )

    # Doluysa GET /api/leads için "X-Admin-Token" başlığı zorunlu olur (boşsa liste herkese açık).
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

    # Render gibi proxy arkasında gerçek ziyaretçi IP'sini almak için
    TRUST_PROXY = False


class GelistirmeConfig(Config):
    """Kendi bilgisayarımızda test ederken: hatalar ayrıntılı görünür."""
    DEBUG = True


class UretimConfig(Config):
    """Render'da yayındayken: hata ayrıntıları gizlenir."""
    DEBUG = False
    TRUST_PROXY = True


# FLASK_ENV değerine göre doğru ayar sınıfını seçmek için
config_secici = {
    "development": GelistirmeConfig,
    "production": UretimConfig,
}
