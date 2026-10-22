"""HTTP rotaları: isteği karşılar, doğrular ve doğru katmana yönlendirir.

Burada SQL veya yapay zekâ kodu YOKTUR; sadece database.py ve ai_service.py fonksiyonları çağrılır.
"""
import hmac
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, current_app
from app.services.ai_service import ai_service, AIServiceError
from app.database import lead_ekle, tum_leadler, VeritabaniHatasi

api = Blueprint("api", __name__)            # /api önekiyle kaydedilir (__init__.py)
sayfalar = Blueprint("sayfalar", __name__)


def _json_govde():
    """İstek gövdesini sözlük olarak döndürür; JSON yoksa veya bozuksa boş sözlük."""
    veri = request.get_json(silent=True)
    return veri if isinstance(veri, dict) else {}


def _metin(veri, alan):
    """Alanı güvenle metne çevirip baştaki/sondaki boşlukları siler."""
    deger = veri.get(alan)
    return deger.strip() if isinstance(deger, str) else ""


def yonetici_gerekli(fonksiyon):
    """ADMIN_TOKEN tanımlıysa "X-Admin-Token" başlığını zorunlu kılar; boşsa herkese açık bırakır."""
    @wraps(fonksiyon)
    def sarmalayici(*args, **kwargs):
        token = current_app.config.get("ADMIN_TOKEN")
        if token:
            gelen = request.headers.get("X-Admin-Token", "")
            # compare_digest: karşılaştırma süresinden anahtar tahmin edilmesini önler
            if not hmac.compare_digest(gelen, token):
                return jsonify({"basari": False, "hata": "Yetkisiz erişim."}), 401
        return fonksiyon(*args, **kwargs)
    return sarmalayici


# ── Sayfalar ──────────────────────────────────────────
@sayfalar.route("/")
def karsilama_sayfasi():
    return render_template("index.html")


@sayfalar.route("/dashboard")
@sayfalar.route("/panel")
def yonetim_paneli():
    return render_template("dashboard.html")


# ── API ───────────────────────────────────────────────
@api.route("/sohbet", methods=["POST"])
def sohbet():
    """Gönderilen: {mesaj, gecmis}  →  Dönen: {basari, cevap}"""
    veri = _json_govde()
    mesaj = _metin(veri, "mesaj")
    if not mesaj:
        return jsonify({"basari": False, "hata": "Mesaj boş olamaz."}), 400

    try:
        cevap = ai_service.yanit_uret(mesaj, veri.get("gecmis", []))
        return jsonify({"basari": True, "cevap": cevap})
    except AIServiceError as e:
        # Yapay zekâ servisi çökerse uygulama çökmez; kibar bir hata döner
        return jsonify({"basari": False, "hata": str(e)}), 503


@api.route("/leads", methods=["POST"])
def lead_kaydet():
    """Gönderilen: {isim, telefon, mesaj?, eposta?, pozisyon?}  →  Dönen: {basari, mesaj}"""
    veri = _json_govde()
    isim = _metin(veri, "isim")
    telefon = _metin(veri, "telefon")
    if not isim or not telefon:
        return jsonify({"basari": False, "hata": "İsim ve telefon zorunludur."}), 400

    try:
        lead_ekle(isim, telefon, _metin(veri, "mesaj"), _metin(veri, "eposta"), _metin(veri, "pozisyon"))
    except VeritabaniHatasi as e:
        return jsonify({"basari": False, "hata": str(e)}), 500
    return jsonify({"basari": True, "mesaj": "Bilgileriniz kaydedildi, en kısa sürede size dönüş yapacağız."}), 201


@api.route("/leads", methods=["GET"])
@yonetici_gerekli
def leadleri_listele():
    """Dönen: {basari, toplam, leadler: [{id, isim, telefon, eposta, pozisyon, mesaj, tarih}]}"""
    try:
        leadler = tum_leadler()
    except VeritabaniHatasi as e:
        return jsonify({"basari": False, "hata": str(e)}), 500
    return jsonify({"basari": True, "toplam": len(leadler), "leadler": leadler})
