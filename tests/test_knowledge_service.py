from app import database
from app.services.knowledge_service import (
    bilgi_servisi, dokumani_parcala, fts_sorgusu_olustur, sadelestir,
)


def basliklar(parcalar):
    return [p["baslik"] for p in parcalar]


def test_sadelestir_turkce_buyuk_harfleri_dogru_cevirir():
    assert sadelestir("İK Işık ŞÇĞÖÜ") == "ik isik scgou"


def test_dokuman_basliklardan_parcalanir_ve_yorumlar_atlanir():
    metin = "# Doküman\n<!-- MOCK -->\n## Bir\nbirinci\n## İki\nikinci"
    parcalar = dokumani_parcala(metin, "urun", 800)
    assert basliklar(parcalar) == ["Doküman › Bir", "Doküman › İki"]
    assert all("MOCK" not in p["icerik"] for p in parcalar)
    assert parcalar[0]["kategori"] == "urun"


def test_uzun_bolum_paragraftan_bolunur():
    paragraf = "kelime " * 30
    metin = "# D\n## Uzun\n" + "\n\n".join([paragraf] * 5)
    parcalar = dokumani_parcala(metin, "urun", 400)
    assert len(parcalar) > 1
    assert all(len(p["icerik"]) <= 400 for p in parcalar)


def test_sorgu_dolgu_kelimelerini_atar_ve_kok_kullanir():
    assert fts_sorgusu_olustur("Açık pozisyonlarınız neler?") == '"acik"* OR "pozis"*'
    assert fts_sorgusu_olustur("merhaba nasılsın ne var") == '"nasil"*'
    assert fts_sorgusu_olustur("merhaba") is None
    assert fts_sorgusu_olustur("") is None


def test_sorgu_ozel_karakterlerle_bozulmaz(app):
    with app.app_context():
        # FTS5 sözdizimi karakterleri sorguya sızmamalı
        assert isinstance(bilgi_servisi.ara('demo" OR * NEAR( ) ^', None, 4), list)


def test_urun_sorusu_urun_parcasini_bulur(app):
    with app.app_context():
        parcalar = bilgi_servisi.ara("Buddy eşleşmesi nasıl çalışıyor?", None, 4)
    assert parcalar[0]["baslik"] == "OnBuddy Ürünü › Akıllı buddy eşleşmesi"


def test_ekli_kelime_onek_aramasiyla_bulunur(app):
    with app.app_context():
        parcalar = bilgi_servisi.ara("Fiyatlarınız ne kadar?", None, 4)
    assert "OnBuddy Ürünü › Fiyatlandırma ve entegrasyonlar" in basliklar(parcalar)


def test_pozisyon_sorusunda_tum_pozisyonlarin_listesi_gelir(app):
    with app.app_context():
        parcalar = bilgi_servisi.ara("Açık pozisyonlarınız neler?", None, 4)
    liste = next(p for p in parcalar if p["baslik"] == "Açık pozisyonlar listesi")
    for baslik in ("Kıdemli Backend Geliştirici", "Mobil Uygulama Geliştirici",
                   "Müşteri Başarı Uzmanı", "İnsan Kaynakları Stajyeri"):
        assert baslik in liste["icerik"]


def test_devam_sorusu_onceki_soruyla_anlasilir(app):
    with app.app_context():
        tek_basina = bilgi_servisi.ara("peki ya stajyer?", None, 4)
        onceki_ile = bilgi_servisi.ara("peki ya stajyer?", "İnsan kaynakları pozisyonları", 4)
    assert "Açık pozisyon › İnsan Kaynakları Stajyeri" in basliklar(onceki_ile)
    assert len(onceki_ile) >= len(tek_basina)


def test_ornek_pozisyonlar_bir_kez_yuklenir(app):
    with app.app_context():
        assert database.pozisyon_sayisi() == 4
        bilgi_servisi.indeksle(app.config)      # ikinci açılış
        assert database.pozisyon_sayisi() == 4


def test_pozisyon_degisince_arama_guncellenir(app):
    with app.app_context():
        yeni_id = database.pozisyon_ekle("Veri Bilimci", "Yazılım", "Uzaktan")
        bilgi_servisi.pozisyonlari_indeksle()
        assert "Açık pozisyon › Veri Bilimci" in basliklar(bilgi_servisi.ara("veri bilimci", None, 4))

        database.pozisyon_aktifligi_degistir(yeni_id, False)
        bilgi_servisi.pozisyonlari_indeksle()
        assert "Açık pozisyon › Veri Bilimci" not in basliklar(bilgi_servisi.ara("veri bilimci", None, 4))


def test_hic_pozisyon_yoksa_bu_bilgi_aranabilir(app):
    with app.app_context():
        for p in database.aktif_pozisyonlar():
            database.pozisyon_aktifligi_degistir(p["id"], False)
        bilgi_servisi.pozisyonlari_indeksle()
        parcalar = bilgi_servisi.ara("açık pozisyon var mı", None, 4)
    liste = next(p for p in parcalar if p["baslik"] == "Açık pozisyonlar listesi")
    assert "açık pozisyon bulunmuyor" in liste["icerik"]


def test_degisen_dokuman_yeniden_indekslenir(app, tmp_path):
    klasor = tmp_path / "bilgi"
    klasor.mkdir()
    (klasor / "cekirdek.md").write_text("çekirdek", encoding="utf-8")
    dosya = klasor / "urun.md"
    dosya.write_text("# Ürün\n## Eski\nkaplumbağa", encoding="utf-8")
    ayarlar = dict(app.config, KNOWLEDGE_DIR=str(klasor))
    with app.app_context():
        bilgi_servisi.indeksle(ayarlar)
        assert bilgi_servisi.ara("kaplumbağa", None, 4)

        dosya.write_text("# Ürün\n## Yeni\nzürafa", encoding="utf-8")
        bilgi_servisi.indeksle(ayarlar)
        assert not bilgi_servisi.ara("kaplumbağa", None, 4)
        assert bilgi_servisi.ara("zürafa", None, 4)

        dosya.unlink()
        bilgi_servisi.indeksle(ayarlar)
        assert not bilgi_servisi.ara("zürafa", None, 4)
