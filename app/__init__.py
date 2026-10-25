import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config_secici
from app.database import init_db


def create_app(config_adi=None, ayarlar=None):
    """Uygulama fabrikası: ayarlar → CORS → veritabanı → bilgi indeksi → rotalar sırasıyla birleştirilir.

    ayarlar: testlerde config değerlerini ezmek için (ör. geçici veritabanı yolu)
    """
    app = Flask(__name__)

    # 1) Ayarları yükle. FLASK_ENV yoksa güvenli taraf olan "production" seçilir (DEBUG kapalı).
    config_adi = config_adi or os.environ.get("FLASK_ENV", "production")
    app.config.from_object(config_secici.get(config_adi, config_secici["production"]))
    if ayarlar:
        app.config.update(ayarlar)

    # Render bir proxy arkasında çalışır; gerçek ziyaretçi IP'si X-Forwarded-For başlığındadır
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # 2) CORS: Wix sitemizin (farklı bir alan adı) bu API'ye istek atabilmesine izin verir.
    #    Hangi sitelerin izinli olduğu .env'deki CORS_ORIGINS ile belirlenir.
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    # 3) Veritabanı tablolarını hazırla (yoksa oluşturur)
    init_db(app)

    # 4) Bilgi dokümanlarını ve pozisyonları arama tablosuna indeksle (değişmeyenler atlanır)
    from app.services.knowledge_service import bilgi_servisi
    from app.services.hiz_siniri import HizSiniri
    with app.app_context():
        bilgi_servisi.indeksle(app.config)
    app.extensions["sohbet_hiz_siniri"] = HizSiniri(
        app.config["CHAT_RATE_LIMIT_REQUESTS"], app.config["CHAT_RATE_LIMIT_WINDOW_SECONDS"]
    )
    app.extensions["lead_hiz_siniri"] = HizSiniri(
        app.config["LEAD_RATE_LIMIT_REQUESTS"], app.config["LEAD_RATE_LIMIT_WINDOW_SECONDS"]
    )

    # 5) Rotaları kaydet; API rotaları /api önekini alır
    from app.routes import api, sayfalar
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(sayfalar)

    @app.route("/health")
    def health():
        """Sunucu canlılık kontrolü (Render ve test için)."""
        return jsonify({"durum": "aktif", "servis": "OnBuddy"}), 200

    @app.errorhandler(RequestEntityTooLarge)
    def cok_buyuk(hata):
        """MAX_CONTENT_LENGTH aşılırsa Wix'e HTML yerine JSON döner."""
        if request.path.startswith("/api/"):
            return jsonify({"basari": False, "hata": "İstek çok büyük."}), 413
        return hata

    return app
