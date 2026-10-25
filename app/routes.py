"""HTTP rotaları: isteği karşılar, doğrular ve doğru katmana yönlendirir.

Burada SQL veya yapay zekâ kodu YOKTUR; sadece database.py ve services/ fonksiyonları çağrılır.
"""
import hmac
import re
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, current_app
from app.services.ai_service import AIServiceError
from app.services.sohbet_service import sohbet_et
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


LEAD_ALAN_SINIRLARI = {"isim": 100, "telefon": 30, "eposta": 254, "pozisyon": 100, "mesaj": 2000}
EPOSTA_DESENI = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TELEFON_DESENI = re.compile(r"^\+?[\d\s()\-]+$")


def _lead_dogrula(veri, isim, telefon):
    """Form alanlarını kontrol eder; sorun varsa kullanıcıya gösterilecek mesajı döndürür."""
    for alan, sinir in LEAD_ALAN_SINIRLARI.items():
        if len(_metin(veri, alan)) > sinir:
            return f"{alan} alanı en fazla {sinir} karakter olabilir."
    rakam_sayisi = sum(c.isdigit() for c in telefon)
    if not TELEFON_DESENI.match(telefon) or not 10 <= rakam_sayisi <= 15:
        return "Lütfen geçerli bir telefon numarası girin."
    eposta = _metin(veri, "eposta")
    if eposta and not EPOSTA_DESENI.match(eposta):
        return "Lütfen geçerli bir e-posta adresi girin."
    return None


def _hata(mesaj, kod, bekleme=None):
    yanit = jsonify({"basari": False, "hata": mesaj})
    if bekleme:
        yanit.headers["Retry-After"] = str(bekleme)
    return yanit, kod


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
    """Gönderilen: {mesaj, gecmis}  →  Dönen: {basari, cevap, yonlendirme}

    yonlendirme: "demo_formu" | "basvuru_formu" | null — Wix'in göstereceği form butonu
    """
    # IP başına sınır: Groq kotasını tek bir ziyaretçi bitiremesin
    bekleme = current_app.extensions["sohbet_hiz_siniri"].izin_ver(request.remote_addr or "bilinmiyor")
    if bekleme:
        return _hata("Çok fazla mesaj gönderdiniz, lütfen biraz sonra tekrar deneyin.", 429, bekleme)

    veri = _json_govde()
    mesaj = _metin(veri, "mesaj")
    if not mesaj:
        return _hata("Mesaj boş olamaz.", 400)
    sinir = current_app.config["CHAT_MESSAGE_MAX_CHARS"]
    if len(mesaj) > sinir:
        return _hata(f"Mesaj en fazla {sinir} karakter olabilir.", 400)
    gecmis = veri.get("gecmis", [])
    if not isinstance(gecmis, list):
        return _hata("gecmis alanı bir liste olmalıdır.", 400)

    try:
        sonuc = sohbet_et(mesaj, gecmis)
    except AIServiceError as e:
        # Yapay zekâ servisi çökerse uygulama çökmez; kibar bir hata döner
        return _hata(str(e), e.durum_kodu)
    except VeritabaniHatasi as e:
        return _hata(str(e), 500)
    return jsonify({"basari": True, "cevap": sonuc["cevap"], "yonlendirme": sonuc["yonlendirme"]})


@api.route("/leads", methods=["POST"])
def lead_kaydet():
    """Gönderilen: {isim, telefon, mesaj?, eposta?, pozisyon?}  →  Dönen: {basari, mesaj}"""
    # IP başına sınır: form sahte kayıtlarla doldurulamasın
    bekleme = current_app.extensions["lead_hiz_siniri"].izin_ver(request.remote_addr or "bilinmiyor")
    if bekleme:
        return _hata("Çok fazla form gönderdiniz, lütfen daha sonra tekrar deneyin.", 429, bekleme)

    veri = _json_govde()
    isim = _metin(veri, "isim")
    telefon = _metin(veri, "telefon")
    if not isim or not telefon:
        return jsonify({"basari": False, "hata": "İsim ve telefon zorunludur."}), 400
    hata = _lead_dogrula(veri, isim, telefon)
    if hata:
        return _hata(hata, 400)

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
