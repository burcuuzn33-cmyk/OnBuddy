import hmac
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, current_app
from app.services.ai_service import ai_service, AIServiceError
from app.database import add_candidate, list_candidates

api = Blueprint("api", __name__)
pages = Blueprint("pages", __name__)


def admin_required(fn):
    """ADMIN_TOKEN tanımlıysa X-Admin-Token başlığını zorunlu kılar."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = current_app.config.get("ADMIN_TOKEN")
        if token:
            sent = request.headers.get("X-Admin-Token", "")
            if not hmac.compare_digest(sent, token):
                return jsonify({"success": False, "error": "Yetkisiz erişim."}), 401
        return fn(*args, **kwargs)
    return wrapper


# ── Sayfalar ──────────────────────────────────────────
@pages.route("/")
def chat_page():
    return render_template("index.html")


@pages.route("/panel")
def admin_panel():
    return render_template("dashboard.html")


# ── API ───────────────────────────────────────────────
@api.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history", [])
    if not message:
        return jsonify({"success": False, "error": "Mesaj boş olamaz."}), 400
    try:
        reply = ai_service.generate_reply(message, history)
        return jsonify({"success": True, "reply": reply})
    except AIServiceError as e:
        return jsonify({"success": False, "error": str(e)}), 503


@api.route("/candidates", methods=["POST"])
def create_candidate():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not name or not email:
        return jsonify({"success": False, "error": "Ad ve e-posta zorunludur."}), 400
    add_candidate(name, email, data.get("phone", ""), data.get("position", ""), data.get("message", ""))
    return jsonify({"success": True, "message": "Bilgileriniz kaydedildi."}), 201


@api.route("/candidates", methods=["GET"])
@admin_required
def get_candidates():
    items = list_candidates()
    return jsonify({"success": True, "total": len(items), "candidates": items})
