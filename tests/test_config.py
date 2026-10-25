import config


def test_varsayilan_sira_gemini_ana_groq_yedek():
    assert config.VARSAYILAN_SAGLAYICI_SIRASI == ["gemini", "groq"]


def test_liste_bos_veya_eksikse_varsayilani_kullanir():
    assert config._liste(None, ["gemini", "groq"]) == ["gemini", "groq"]
    assert config._liste("  , ", ["gemini", "groq"]) == ["gemini", "groq"]


def test_liste_sirayi_korur_ve_kucuk_harfe_cevirir():
    assert config._liste(" Groq , GEMINI", ["x"]) == ["groq", "gemini"]
