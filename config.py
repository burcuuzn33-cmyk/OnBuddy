import os
from dotenv import load_dotenv

# .env dosyasındaki değerleri ortam değişkenlerine yükler.
# En başta çağrılmalı; yoksa aşağıdaki os.environ.get(...) satırları .env'i göremez.
load_dotenv()


def _origin_listesi(deger):
    """CORS için 'https://a.com, https://b.com' metnini listeye çevirir. '*' herkese izin verir."""
    deger = (deger or "*").strip()
    if deger == "*":
        return "*"
    return [o.strip() for o in deger.split(",") if o.strip()]


class Config:
    """Tüm ayarlar tek yerde. Her değer önce .env'den okunur, yoksa güvenli varsayılan kullanılır."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "gelistirme-icin-gizli-anahtar")
    DATABASE_URL = os.environ.get("DATABASE_URL", "onbuddy.db")

    # Yapay zekâ sağlayıcısı: groq (önerilen, ücretsiz) | openai | gemini
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # Hangi sitelerin (ör. Wix sitemiz) API'ye istek atabileceği.
    # Geliştirmede "*", canlıda kendi Wix adresimiz: https://kullanici.wixstudio.com
    # (Eski isim CORS_ALLOWED_ORIGINS da desteklenir.)
    CORS_ORIGINS = _origin_listesi(
        os.environ.get("CORS_ORIGINS") or os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    )

    # Doluysa GET /api/leads için "X-Admin-Token" başlığı zorunlu olur (boşsa liste herkese açık).
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

    # Yapay zekânın kişiliği — projeyi OnBuddy'ye özel yapan tek metin burası.
    BUSINESS_CONTEXT = os.environ.get(
        "BUSINESS_CONTEXT",
        "Sen OnBuddy'nin İK asistanısın. Adaylara ve çalışanlara kısa, kibar ve profesyonel "
        "Türkçe yanıtlar ver. Açık pozisyonlar, başvuru süreci ve işe alım sorularını yanıtla; "
        "uygun olduğunda adayı iletişim bilgilerini bırakmaya yönlendir.",
    )


class GelistirmeConfig(Config):
    """Kendi bilgisayarımızda test ederken: hatalar ayrıntılı görünür."""
    DEBUG = True


class UretimConfig(Config):
    """Render'da yayındayken: hata ayrıntıları gizlenir."""
    DEBUG = False


# FLASK_ENV değerine göre doğru ayar sınıfını seçmek için
config_secici = {
    "development": GelistirmeConfig,
    "production": UretimConfig,
}
