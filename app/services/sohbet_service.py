"""Sohbet akışı: günlük bütçe → bilgi araması → Groq → kullanım kaydı → yönlendirme.

Rotalar sadece bu fonksiyonu çağırır; arama, yapay zekâ ve veritabanı adımlarını burası birleştirir.
"""
import logging
from collections import Counter

from flask import current_app

from app import database
from app.services.ai_service import ai_service, AIServiceError
from app.services.knowledge_service import bilgi_servisi

log = logging.getLogger(__name__)

BUTCE_DOLDU_YANITI = (
    "Asistanımız bugünlük yoğunluk sınırına ulaştı. Sorunuzu iletmek için demo veya başvuru "
    "formunu kullanabilir ya da info@onbuddy.com adresine yazabilirsiniz."
)

# Bulunan parçaların kategorisine göre Wix'in göstereceği form butonu
YONLENDIRME = {
    "urun": "demo_formu",
    "sirket": "demo_formu",
    "kariyer": "basvuru_formu",
    "pozisyon": "basvuru_formu",
}


def sohbet_et(mesaj, gecmis):
    """Dönen: {"cevap", "yonlendirme"}. Yapay zekâ hatasında AIServiceError fırlatır."""
    ayarlar = current_app.config

    if database.bugunku_token_toplami() >= ayarlar["AI_DAILY_TOKEN_BUDGET"]:
        log.warning("Günlük token bütçesi doldu, Groq'a gidilmedi.")
        return {"cevap": BUTCE_DOLDU_YANITI, "yonlendirme": None}

    parcalar = bilgi_servisi.ara(mesaj, _onceki_kullanici_mesaji(gecmis), ayarlar["RAG_TOP_K"])

    try:
        sonuc = ai_service.yanit_uret(mesaj, gecmis, bilgi_servisi.cekirdek(ayarlar), parcalar)
    except AIServiceError as e:
        _kullanim_kaydet(e.model, 0, 0, None, "kota" if e.durum_kodu == 429 else "hata")
        raise

    if not sonuc.demo:
        _kullanim_kaydet(sonuc.model, sonuc.prompt_token, sonuc.cevap_token, sonuc.sure_ms, "basarili")
    return {"cevap": sonuc.cevap, "yonlendirme": yonlendirme_bul(parcalar)}


def yonlendirme_bul(parcalar):
    """Parçaların çoğunluğu hangi alandansa o formu önerir; ek bir yapay zekâ çağrısı gerekmez.

    Eşitlikte en alakalı (ilk) parçanın alanı kazanır. Parça yoksa None.
    """
    hedefler = [YONLENDIRME[p["kategori"]] for p in parcalar if p["kategori"] in YONLENDIRME]
    if not hedefler:
        return None
    sayilar = Counter(hedefler)
    en_cok = max(sayilar.values())
    return next(h for h in hedefler if sayilar[h] == en_cok)


def _onceki_kullanici_mesaji(gecmis):
    if not isinstance(gecmis, list):
        return None
    for m in reversed(gecmis):
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return None


def _kullanim_kaydet(model, prompt_token, cevap_token, sure_ms, durum):
    # Kayıt yazılamazsa kullanıcının cevabı yine de dönmeli
    try:
        database.ai_kullanim_ekle(model, prompt_token, cevap_token, sure_ms, durum)
    except database.VeritabaniHatasi:
        log.exception("Yapay zekâ kullanım kaydı yazılamadı.")
