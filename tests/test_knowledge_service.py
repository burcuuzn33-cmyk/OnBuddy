import pytest

from app import create_app
from app.services.knowledge_service import (
    BILGI_UYARI_KARAKTER, BilgiHatasi, BilgiServisi, temizle,
)


def klasor_hazirla(tmp_path, belge="# Asistan\n## Bir\nbirinci"):
    klasor = tmp_path / "bilgi"
    klasor.mkdir()
    if belge is not None:
        (klasor / "asistan.md").write_text(belge, encoding="utf-8")
    return klasor, {"KNOWLEDGE_DIR": str(klasor)}


def test_temizle_yorumlari_atar_ve_bosluklari_toplar():
    metin = "# D\n<!-- not\nçok satırlı -->\n\n\n\n## Bir\nmetin <!-- satır içi --> devam"
    assert temizle(metin) == "# D\n\n## Bir\nmetin  devam"


def test_belge_tek_parca_ve_eksiksiz_okunur(tmp_path):
    _, ayar = klasor_hazirla(tmp_path, belge="# B\n## Bir\nbirinci\n\n## İki\nikinci")
    assert BilgiServisi().belge(ayar) == "# B\n## Bir\nbirinci\n\n## İki\nikinci"


def test_gercek_asistan_dosyasi_yuklenir(app):
    belge = BilgiServisi().belge(app.config)
    # Kurallar ve bilgi aynı belgede; bilgi <bilgi> etiketleri arasında
    assert "[FORM:demo]" in belge and "Kesin kurallar" in belge
    assert belge.index("<bilgi>") < belge.index("OnBuddy nedir?") < belge.index("</bilgi>")
    assert "Fiyatlandırma" in belge
    assert "<!--" not in belge
    assert len(belge) < BILGI_UYARI_KARAKTER


def test_dosya_degisince_yeniden_okunur(tmp_path):
    klasor, ayar = klasor_hazirla(tmp_path, belge="eski")
    servis = BilgiServisi()
    assert servis.belge(ayar) == "eski"
    dosya = klasor / "asistan.md"
    dosya.write_text("yeni ve daha uzun", encoding="utf-8")
    assert servis.belge(ayar) == "yeni ve daha uzun"


@pytest.mark.parametrize("belge", [None, "<!-- sadece yorum -->", "  "])
def test_eksik_veya_bos_dosyada_acilis_basarisiz_olur(tmp_path, belge):
    _, ayar = klasor_hazirla(tmp_path, belge)
    with pytest.raises(BilgiHatasi):
        BilgiServisi().dogrula(ayar)


def test_uygulama_asistan_dosyasi_olmadan_acilmaz(tmp_path):
    with pytest.raises(BilgiHatasi):
        create_app("development", {
            "DATABASE_URL": str(tmp_path / "t.db"), "KNOWLEDGE_DIR": str(tmp_path / "yok"),
        })


def test_uzun_belgede_uyari_yazilir(tmp_path, caplog):
    _, ayar = klasor_hazirla(tmp_path, belge="a" * (BILGI_UYARI_KARAKTER + 1))
    with caplog.at_level("WARNING"):
        BilgiServisi().dogrula(ayar)
    assert "asistan.md" in caplog.text and "uzun" in caplog.text
