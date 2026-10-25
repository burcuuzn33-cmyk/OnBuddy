import dotenv
import pytest

# Testler geliştiricinin .env dosyasından etkilenmez (ADMIN_TOKEN, hız sınırları, modeller...).
# config.py içe aktarılmadan önce çalışmalı; conftest.py bundan önce yüklenir.
dotenv.load_dotenv = lambda *args, **kwargs: False

from app import create_app
from config import Config


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Testler gerçek Groq'a gitmez; anahtar varsayılan olarak boş (demo modu)
    monkeypatch.setattr(Config, "GROQ_API_KEY", "")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    return create_app("development", {"DATABASE_URL": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


class SahteYanit:
    """requests.post'un döndürdüğü yanıtı taklit eder."""

    def __init__(self, durum=200, veri=None):
        self.status_code = durum
        self._veri = veri
        self.text = str(veri)

    def json(self):
        if self._veri is None:
            raise ValueError("JSON yok")
        return self._veri


def groq_cevabi(icerik="Merhaba!", bitis="stop", prompt=100, cevap=20):
    return SahteYanit(200, {
        "choices": [{"message": {"content": icerik}, "finish_reason": bitis}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": cevap},
    })


@pytest.fixture
def groq(monkeypatch):
    """Groq'u taklit eder: sıradaki yanıtları verir, gönderilen istekleri kaydeder."""
    monkeypatch.setattr(Config, "GROQ_API_KEY", "test-anahtari")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")     # yedek isteyen testler kendisi açar

    class Sahte:
        yanitlar = []
        istekler = []
        adresler = []
        zaman_asimlari = []

        def post(self, url, json=None, headers=None, timeout=None):
            self.adresler.append(url)
            self.zaman_asimlari.append(timeout)
            self.istekler.append(json)
            yanit = self.yanitlar.pop(0)
            if isinstance(yanit, Exception):
                raise yanit
            return yanit

    sahte = Sahte()
    sahte.yanitlar, sahte.istekler, sahte.adresler, sahte.zaman_asimlari = [], [], [], []
    monkeypatch.setattr("app.services.ai_service.requests.post", sahte.post)
    return sahte
