import pytest

from app import create_app

GECERLI = {"isim": "Ayşe Yılmaz", "telefon": "0532 123 45 67", "eposta": "ayse@sirket.com", "mesaj": "Demo istiyorum"}


def test_gecerli_form_kaydedilir_ve_listelenir(client):
    r = client.post("/api/leads", json=GECERLI)
    assert r.status_code == 201 and r.get_json()["basari"] is True
    liste = client.get("/api/leads").get_json()
    assert liste["toplam"] == 1
    kayit = liste["leadler"][0]
    assert (kayit["isim"], kayit["telefon"], kayit["eposta"], kayit["mesaj"]) == (
        "Ayşe Yılmaz", "0532 123 45 67", "ayse@sirket.com", "Demo istiyorum")


def test_eposta_ve_mesaj_istege_bagli(client):
    r = client.post("/api/leads", json={"isim": "Ali", "telefon": "+90 532 123 45 67"})
    assert r.status_code == 201


@pytest.mark.parametrize("degisiklik, beklenen", [
    ({"isim": ""}, "İsim ve telefon zorunludur."),
    ({"telefon": "12345"}, "Lütfen geçerli bir telefon numarası girin."),
    ({"telefon": "0532-ABC-4567"}, "Lütfen geçerli bir telefon numarası girin."),
    ({"eposta": "gecersiz-adres"}, "Lütfen geçerli bir e-posta adresi girin."),
    ({"isim": "x" * 101}, "isim alanı en fazla 100 karakter olabilir."),
    ({"mesaj": "x" * 2001}, "mesaj alanı en fazla 2000 karakter olabilir."),
])
def test_hatali_form_reddedilir(client, degisiklik, beklenen):
    r = client.post("/api/leads", json={**GECERLI, **degisiklik})
    assert r.status_code == 400 and r.get_json()["hata"] == beklenen
    assert client.get("/api/leads").get_json()["toplam"] == 0


def test_form_ip_basina_sinirli(tmp_path):
    app = create_app("development", {"DATABASE_URL": str(tmp_path / "t.db"), "LEAD_RATE_LIMIT_REQUESTS": 2})
    client = app.test_client()
    for _ in range(2):
        assert client.post("/api/leads", json=GECERLI).status_code == 201
    r = client.post("/api/leads", json=GECERLI)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_admin_token_varsa_liste_korunur(tmp_path):
    app = create_app("development", {"DATABASE_URL": str(tmp_path / "t.db"), "ADMIN_TOKEN": "gizli-test"})
    client = app.test_client()
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads", headers={"X-Admin-Token": "yanlis"}).status_code == 401
    assert client.get("/api/leads", headers={"X-Admin-Token": "gizli-test"}).status_code == 200
