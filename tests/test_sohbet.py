import pytest

from app import create_app, database
from app.services.sohbet_service import yonlendirme_bul, BUTCE_DOLDU_YANITI
from tests.conftest import SahteYanit, groq_cevabi


def kullanim_kayitlari(app):
    with app.app_context():
        baglanti = database.get_db()
        try:
            return [dict(s) for s in baglanti.execute("SELECT model, prompt_token, cevap_token, durum FROM ai_kullanim")]
        finally:
            baglanti.close()


def test_sohbet_cevap_ve_yonlendirme_doner(client, groq):
    groq.yanitlar.append(groq_cevabi("Açık pozisyonlarımız şunlar..."))
    r = client.post("/api/sohbet", json={"mesaj": "Açık pozisyonlarınız neler?"})
    assert r.status_code == 200
    assert r.get_json() == {"basari": True, "cevap": "Açık pozisyonlarımız şunlar...", "yonlendirme": "basvuru_formu"}
    # Bulunan pozisyon bilgisi sistem mesajına eklenmiş olmalı
    assert "Kıdemli Backend Geliştirici" in groq.istekler[0]["messages"][0]["content"]


def test_urun_sorusu_demo_formuna_yonlendirir(client, groq):
    groq.yanitlar.append(groq_cevabi("15 dakikalık demo..."))
    r = client.post("/api/sohbet", json={"mesaj": "Kurumsal demo ve ücretsiz deneme nasıl oluyor?"})
    assert r.get_json()["yonlendirme"] == "demo_formu"


def test_selamlasmada_yonlendirme_yok(client, groq):
    groq.yanitlar.append(groq_cevabi("Merhaba!"))
    r = client.post("/api/sohbet", json={"mesaj": "merhaba"})
    assert r.get_json()["yonlendirme"] is None


def test_kullanim_kaydi_icerik_tutmadan_yazilir(app, client, groq):
    groq.yanitlar.append(groq_cevabi("tamam", prompt=900, cevap=40))
    client.post("/api/sohbet", json={"mesaj": "demo"})
    assert kullanim_kayitlari(app) == [
        {"model": "llama-3.3-70b-versatile", "prompt_token": 900, "cevap_token": 40, "durum": "basarili"}
    ]


def test_kota_hatasi_429_doner_ve_kaydedilir(app, client, groq):
    groq.yanitlar += [SahteYanit(429, {}), SahteYanit(429, {})]
    r = client.post("/api/sohbet", json={"mesaj": "demo"})
    assert r.status_code == 429 and r.get_json()["basari"] is False
    assert kullanim_kayitlari(app)[0]["durum"] == "kota"


def test_gunluk_butce_dolunca_groqa_gidilmez(app, client, groq):
    app.config["AI_DAILY_TOKEN_BUDGET"] = 1000
    with app.app_context():
        database.ai_kullanim_ekle("llama-3.3-70b-versatile", 900, 100, 10, "basarili")
    r = client.post("/api/sohbet", json={"mesaj": "demo"})
    assert r.get_json()["cevap"] == BUTCE_DOLDU_YANITI
    assert groq.istekler == []


def test_demo_modunda_kullanim_kaydi_yazilmaz(app, client):
    client.post("/api/sohbet", json={"mesaj": "demo"})
    assert kullanim_kayitlari(app) == []


@pytest.mark.parametrize("govde, beklenen", [
    ({}, "Mesaj boş olamaz."),
    ({"mesaj": "   "}, "Mesaj boş olamaz."),
    ({"mesaj": "x" * 1001}, "Mesaj en fazla 1000 karakter olabilir."),
    ({"mesaj": "selam", "gecmis": "bozuk"}, "gecmis alanı bir liste olmalıdır."),
])
def test_dogrulama_hatalari(client, govde, beklenen):
    r = client.post("/api/sohbet", json=govde)
    assert r.status_code == 400 and r.get_json()["hata"] == beklenen


def test_ip_basina_hiz_siniri(tmp_path):
    app = create_app("development", {
        "DATABASE_URL": str(tmp_path / "t.db"), "CHAT_RATE_LIMIT_REQUESTS": 2,
    })
    client = app.test_client()
    for _ in range(2):
        assert client.post("/api/sohbet", json={"mesaj": "selam"}).status_code == 200
    r = client.post("/api/sohbet", json={"mesaj": "selam"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_cok_buyuk_istek_json_413(tmp_path):
    app = create_app("development", {"DATABASE_URL": str(tmp_path / "t.db"), "MAX_CONTENT_LENGTH": 100})
    r = app.test_client().post("/api/sohbet", json={"mesaj": "x" * 500})
    assert r.status_code == 413 and r.get_json()["basari"] is False


@pytest.mark.parametrize("kategoriler, beklenen", [
    ([], None),
    (["urun", "sirket"], "demo_formu"),
    (["kariyer", "pozisyon", "urun"], "basvuru_formu"),
    (["urun", "pozisyon"], "demo_formu"),          # eşitlikte en alakalı (ilk) parça kazanır
])
def test_yonlendirme_kurali(kategoriler, beklenen):
    assert yonlendirme_bul([{"kategori": k} for k in kategoriler]) == beklenen
