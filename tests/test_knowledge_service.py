import pytest

from app import create_app
from app.services.knowledge_service import (
    BILGI_UYARI_KARAKTER, BilgiHatasi, BilgiServisi, temizle,
)


def klasor_hazirla(tmp_path, cekirdek="çekirdek", bilgi="# Bilgi\n## Bir\nbirinci"):
    klasor = tmp_path / "bilgi"
    klasor.mkdir()
    if cekirdek is not None:
        (klasor / "cekirdek.md").write_text(cekirdek, encoding="utf-8")
    if bilgi is not None:
        (klasor / "bilgi.md").write_text(bilgi, encoding="utf-8")
    return klasor, {"KNOWLEDGE_DIR": str(klasor)}


def test_temizle_yorumlari_atar_ve_bosluklari_toplar():
    metin = "# D\n<!-- not\nçok satırlı -->\n\n\n\n## Bir\nmetin <!-- satır içi --> devam"
    assert temizle(metin) == "# D\n\n## Bir\nmetin  devam"


def test_bilgi_belgesi_tek_parca_ve_eksiksiz_okunur(tmp_path):
    _, ayar = klasor_hazirla(tmp_path, bilgi="# B\n## Bir\nbirinci\n\n## İki\nikinci")
    assert BilgiServisi().bilgi(ayar) == "# B\n## Bir\nbirinci\n\n## İki\nikinci"


def test_gercek_bilgi_dosyasi_yuklenir(app):
    bilgi = BilgiServisi().bilgi(app.config)
    assert "OnBuddy nedir?" in bilgi and "Fiyatlandırma" in bilgi
    assert "<!--" not in bilgi
    assert len(bilgi) < BILGI_UYARI_KARAKTER


def test_dosya_degisince_yeniden_okunur(tmp_path):
    klasor, ayar = klasor_hazirla(tmp_path, bilgi="eski")
    servis = BilgiServisi()
    assert servis.bilgi(ayar) == "eski"
    dosya = klasor / "bilgi.md"
    dosya.write_text("yeni ve daha uzun", encoding="utf-8")
    assert servis.bilgi(ayar) == "yeni ve daha uzun"


@pytest.mark.parametrize("cekirdek, bilgi", [(None, "x"), ("x", None), ("x", "<!-- sadece yorum -->"), ("  ", "x")])
def test_eksik_veya_bos_dosyada_acilis_basarisiz_olur(tmp_path, cekirdek, bilgi):
    _, ayar = klasor_hazirla(tmp_path, cekirdek, bilgi)
    with pytest.raises(BilgiHatasi):
        BilgiServisi().dogrula(ayar)


def test_uygulama_bilgi_dosyasi_olmadan_acilmaz(tmp_path):
    with pytest.raises(BilgiHatasi):
        create_app("development", {
            "DATABASE_URL": str(tmp_path / "t.db"), "KNOWLEDGE_DIR": str(tmp_path / "yok"),
        })


def test_uzun_belgede_uyari_yazilir(tmp_path, caplog):
    _, ayar = klasor_hazirla(tmp_path, bilgi="a" * (BILGI_UYARI_KARAKTER + 1))
    with caplog.at_level("WARNING"):
        BilgiServisi().dogrula(ayar)
    assert "bilgi.md" in caplog.text and "uzun" in caplog.text
