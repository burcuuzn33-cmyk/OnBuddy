"""Yapay zekâ servis katmanı: tüm AI API çağrıları yalnızca bu dosyada bulunur.

Bu dosya Flask, HTTP rotaları veya veritabanı hakkında hiçbir şey bilmez;
sadece mesajı alır, seçili yapay zekâya sorar ve yanıt metnini döndürür.
"""
import logging
import requests
from config import Config

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
ZAMAN_ASIMI = 15        # saniye; yapay zekâ bu sürede yanıt vermezse vazgeçilir
MAKS_GECMIS = 10        # token limitini aşmamak için gönderilen son mesaj sayısı


class AIServiceError(Exception):
    """Yapay zekâ servisine ulaşılamadığında fırlatılır; rotalar bunu 503 JSON'a çevirir."""


class AIService:
    def yanit_uret(self, mesaj, gecmis=None):
        """AI_PROVIDER ayarına göre doğru sağlayıcıyı seçer ve yanıt metnini döndürür."""
        gecmis = self._gecmisi_temizle(gecmis)
        saglayici = (Config.AI_PROVIDER or "groq").lower()

        if saglayici == "openai":
            return self._openai_uyumlu_cagir(OPENAI_URL, Config.OPENAI_API_KEY, "gpt-4o-mini", mesaj, gecmis, "OpenAI")
        if saglayici == "gemini":
            return self._gemini_cagir(mesaj, gecmis)
        # Varsayılan: Groq (ücretsiz ve hızlı)
        return self._openai_uyumlu_cagir(GROQ_URL, Config.GROQ_API_KEY, Config.GROQ_MODEL, mesaj, gecmis, "Groq")

    def _sistem_talimati(self):
        """Yapay zekâya kim olduğunu söyleyen BUSINESS_CONTEXT metni."""
        return Config.BUSINESS_CONTEXT

    @staticmethod
    def _gecmisi_temizle(gecmis):
        """Frontend'den gelen geçmişte sadece geçerli {role, content} kayıtlarını tutar."""
        if not isinstance(gecmis, list):
            return []
        temiz = [
            {"role": m["role"], "content": m["content"]}
            for m in gecmis
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
        ]
        return temiz[-MAKS_GECMIS:]

    def _openai_uyumlu_cagir(self, url, api_anahtari, model, mesaj, gecmis, ad):
        """Groq ve OpenAI aynı formatı kullandığı için ikisi de bu metottan geçer."""
        if not api_anahtari:
            log.warning("%s API anahtarı yok, demo modunda yanıt veriliyor.", ad)
            return self._demo_yaniti()

        # Sıra önemli: önce sistem talimatı, sonra geçmiş, en sonda yeni kullanıcı mesajı
        mesajlar = [{"role": "system", "content": self._sistem_talimati()}]
        mesajlar += gecmis
        mesajlar.append({"role": "user", "content": mesaj})

        try:
            yanit = requests.post(
                url,
                json={"model": model, "messages": mesajlar, "max_tokens": 500, "temperature": 0.7},
                headers={"Authorization": f"Bearer {api_anahtari}"},
                timeout=ZAMAN_ASIMI,
            )
            if yanit.status_code != 200:
                log.error("%s HTTP %s: %s", ad, yanit.status_code, yanit.text[:300])
                raise AIServiceError(f"{ad} servisi şu an yanıt veremiyor (HTTP {yanit.status_code}).")
            return yanit.json()["choices"][0]["message"]["content"].strip()
        except AIServiceError:
            raise
        except Exception as e:
            log.error("%s bağlantı hatası: %s", ad, e)
            raise AIServiceError(f"{ad} servisine bağlanılamadı.") from e

    def _gemini_cagir(self, mesaj, gecmis):
        if not Config.GEMINI_API_KEY:
            return self._demo_yaniti()

        # Gemini'de asistan rolünün adı "model"dir
        icerik = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in gecmis
        ]
        icerik.append({"role": "user", "parts": [{"text": mesaj}]})

        try:
            yanit = requests.post(
                GEMINI_URL,
                json={
                    "system_instruction": {"parts": [{"text": self._sistem_talimati()}]},
                    "contents": icerik,
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
                },
                headers={"x-goog-api-key": Config.GEMINI_API_KEY},
                timeout=ZAMAN_ASIMI,
            )
            yanit.raise_for_status()
            return yanit.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            log.error("Gemini hatası: %s", e)
            raise AIServiceError("Gemini servisine ulaşılamadı.") from e

    @staticmethod
    def _demo_yaniti():
        """API anahtarı yoksa çökmek yerine bu bilgilendirme mesajı döner."""
        return "Sistem demo modunda çalışıyor: API anahtarı tanımlı değil. Lütfen .env dosyanızı kontrol edin."


# Tüm uygulamanın kullandığı tek örnek
ai_service = AIService()
