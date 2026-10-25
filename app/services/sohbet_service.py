"""Sohbet akışı: günlük bütçe → Groq → kullanım kaydı → yönlendirme.

Rotalar sadece bu fonksiyonu çağırır; yapay zekâ ve veritabanı adımlarını burası birleştirir.
"""
import logging
import re

from flask import current_app

from app import database
from app.services.ai_service import ai_service, AIServiceError
from app.services.knowledge_service import bilgi_servisi

log = logging.getLogger(__name__)

BUTCE_DOLDU_YANITI = (
    "Asistanımız bugünlük yoğunluk sınırına ulaştı. Sorunuzu iletmek için demo veya başvuru "
    "formunu kullanabilir ya da info@onbuddy.com adresine yazabilirsiniz."
)

# Model, form önerirken cevabın sonuna [FORM:demo] veya [FORM:basvuru] ekler (bkz. knowledge/cekirdek.md).
# Etiket kullanıcıya gösterilmez; Wix'in göstereceği form butonuna çevrilir.
FORM_ETIKETI = re.compile(r"\[\s*FORM\s*:\s*(demo|basvuru)\s*\]", re.IGNORECASE)
YONLENDIRME = {"demo": "demo_formu", "basvuru": "basvuru_formu"}


def sohbet_et(mesaj, gecmis):
    """Dönen: {"cevap", "yonlendirme"}. Yapay zekâ hatasında AIServiceError fırlatır."""
    ayarlar = current_app.config

    if database.bugunku_token_toplami() >= ayarlar["AI_DAILY_TOKEN_BUDGET"]:
        log.warning("Günlük token bütçesi doldu, Groq'a gidilmedi.")
        return {"cevap": BUTCE_DOLDU_YANITI, "yonlendirme": None}

    try:
        sonuc = ai_service.yanit_uret(
            mesaj, gecmis, bilgi_servisi.cekirdek(ayarlar), bilgi_servisi.bilgi(ayarlar)
        )
    except AIServiceError as e:
        _kullanim_kaydet(e.model, 0, 0, None, "kota" if e.durum_kodu == 429 else "hata")
        raise

    if not sonuc.demo:
        _kullanim_kaydet(sonuc.model, sonuc.prompt_token, sonuc.cevap_token, sonuc.sure_ms, "basarili")
    cevap, yonlendirme = yonlendirmeyi_ayir(sonuc.cevap)
    return {"cevap": cevap, "yonlendirme": yonlendirme}


def yonlendirmeyi_ayir(cevap):
    """Cevaptaki [FORM:...] etiketini ayırır. Dönen: (etiketsiz cevap, "demo_formu" | "basvuru_formu" | None).

    Birden fazla etiket varsa sonuncusu geçerlidir. Etiketsiz cevapta yönlendirme yoktur.
    """
    etiketler = FORM_ETIKETI.findall(cevap)
    temiz = FORM_ETIKETI.sub("", cevap).strip()
    return temiz, (YONLENDIRME[etiketler[-1].lower()] if etiketler else None)


def _kullanim_kaydet(model, prompt_token, cevap_token, sure_ms, durum):
    # Kayıt yazılamazsa kullanıcının cevabı yine de dönmeli
    try:
        database.ai_kullanim_ekle(model, prompt_token, cevap_token, sure_ms, durum)
    except database.VeritabaniHatasi:
        log.exception("Yapay zekâ kullanım kaydı yazılamadı.")
