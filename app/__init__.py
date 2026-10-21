from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from app.database import init_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        origins=app.config["CORS_ALLOWED_ORIGINS"],
        methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    init_db(app)

    from app.routes import api, pages
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(pages)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "OnBuddy"}), 200

    return app
