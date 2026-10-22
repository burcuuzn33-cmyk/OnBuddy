import os
from flask import Flask, jsonify
from flask_cors import CORS
from config import config_secici
from app.database import init_db


def create_app(config_adi=None):
    """Uygulama fabrikası: ayarlar → CORS → veritabanı → rotalar sırasıyla birleştirilir."""
    app = Flask(__name__)

    # 1) Ayarları yükle. FLASK_ENV yoksa güvenli taraf olan "production" seçilir (DEBUG kapalı).
    config_adi = config_adi or os.environ.get("FLASK_ENV", "production")
    app.config.from_object(config_secici.get(config_adi, config_secici["production"]))

    # 2) CORS: Wix sitemizin (farklı bir alan adı) bu API'ye istek atabilmesine izin verir.
    #    Hangi sitelerin izinli olduğu .env'deki CORS_ORIGINS ile belirlenir.
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    # 3) Veritabanı tablosunu hazırla (yoksa oluşturur)
    init_db(app)

    # 4) Rotaları kaydet; API rotaları /api önekini alır
    from app.routes import api, sayfalar
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(sayfalar)

    @app.route("/health")
    def health():
        """Sunucu canlılık kontrolü (Render ve test için)."""
        return jsonify({"durum": "aktif", "servis": "OnBuddy"}), 200

    return app
