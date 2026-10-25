import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasındaki değerleri ortam değişkenlerine yükler.
# En başta çağrılmalı; yoksa aşağıdaki os.environ.get(...) satırları .env'i göremez.
load_dotenv()

PROJE_KLASORU = Path(__file__).resolve().parent

# Ana sağlayıcı Gemini, yedek Groq. (Groq bu hesapta dakikada yalnızca 8.000 token verdiği için,
# istek başına yaklaşık 3.000 token harcayan bu asistanda dakikada 2-3 isteğe yetiyor.)
VARSAYILAN_SAGLAYICI_SIRASI = ["gemini", "groq"]


def _origin_listesi(deger):
    """CORS için 'https://a.com, https://b.com' metnini listeye çevirir. '*' herkese izin verir."""
    deger = (deger or "*").strip()
    if deger == "*":
        return "*"
    return [o.strip() for o in deger.split(",") if o.strip()]


def _liste(deger, varsayilan):
    """'groq, gemini' metnini küçük harfli listeye çevirir; boşsa varsayılanı kullanır."""
    ogeler = [o.strip().lower() for o in (deger or "").split(",") if o.strip()]
    return ogeler or varsayilan


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

    # Yapay zekâ: iki sağlayıcı sırayla denenir (AI_PROVIDER_ORDER; varsayılan: Gemini, olmazsa Groq). Ana sağlayıcıdan geçerli cevap
    # alınamazsa (kota, zaman aşımı, sunucu hatası, boş cevap...) sıradakine geçilir. Anahtarı olmayan
    # sağlayıcı atlanır; hiçbirinin anahtarı yoksa sistem demo modunda çalışır.
    # Not: Bu Groq hesabının Llama modellerine erişimi yok (model_not_found); gpt-oss modelleri kullanılır.
    AI_PROVIDER_ORDER = _liste(os.environ.get("AI_PROVIDER_ORDER"), VARSAYILAN_SAGLAYICI_SIRASI)
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    # gpt-oss "düşünen" modeldir: düşünme kısa tutulur ve cevapta gönderilmez. Boşsa parametre gönderilmez.
    AI_REASONING_EFFORT = os.environ.get("AI_REASONING_EFFORT", "low").strip()
    AI_TEMPERATURE = _sayi("AI_TEMPERATURE", 0.3, float)
    # Düşünme token'ları da bu sınırdan yer (Gemini'de görünmez, usage'a yazılmaz bile): sınır dar olursa kısa bir
    # cevap bile finish_reason=length ile 'yarım' sayılır. 250 kelimelik cevap yaklaşık 600 token tutar.
    AI_MAX_TOKENS = _sayi("AI_MAX_TOKENS", 2000)
    # İstek başına zaman aşımı ve tüm sağlayıcılar için toplam süre (saniye). Toplam süre, gunicorn'un
    # varsayılan 30 sn'lik sınırının altında kalmalı; yoksa çalışan öldürülür ve Wix JSON yerine HTML hata alır.
    AI_TIMEOUT = _sayi("AI_TIMEOUT", 10)
    AI_TOTAL_TIMEOUT = _sayi("AI_TOTAL_TIMEOUT", 25)
    AI_HISTORY_MAX_MESSAGES = _sayi("AI_HISTORY_MAX_MESSAGES", 6)
    AI_HISTORY_MAX_CHARS = _sayi("AI_HISTORY_MAX_CHARS", 2400)
    # Günlük toplam token sınırı; aşılırsa Groq'a gidilmez (kota birinin yüzünden bitmesin)
    AI_DAILY_TOKEN_BUDGET = _sayi("AI_DAILY_TOKEN_BUDGET", 300000)

    # Bilgi klasörü: asistan.md (kurallar + bilgi tek belgede, her soruda gönderilir)
    KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", str(PROJE_KLASORU / "knowledge"))

    # Kötüye kullanım koruması: IP başına sohbet sınırı ve istek gövdesi boyutu
    CHAT_RATE_LIMIT_REQUESTS = _sayi("CHAT_RATE_LIMIT_REQUESTS", 10)
    CHAT_RATE_LIMIT_WINDOW_SECONDS = _sayi("CHAT_RATE_LIMIT_WINDOW_SECONDS", 60)
    CHAT_MESSAGE_MAX_CHARS = _sayi("CHAT_MESSAGE_MAX_CHARS", 1000)
    # Form (POST /api/leads): IP başına 10 dakikada en fazla 5 kayıt
    LEAD_RATE_LIMIT_REQUESTS = _sayi("LEAD_RATE_LIMIT_REQUESTS", 5)
    LEAD_RATE_LIMIT_WINDOW_SECONDS = _sayi("LEAD_RATE_LIMIT_WINDOW_SECONDS", 600)
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
