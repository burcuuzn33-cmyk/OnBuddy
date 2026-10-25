"""Yapay zekâ servis katmanı: tüm Groq API çağrıları yalnızca bu dosyada bulunur.

Bu dosya Flask, HTTP rotaları veya veritabanı hakkında hiçbir şey bilmez;
sistem mesajını, geçmişi ve bilgi belgesini alır, Groq'a sorar ve sonucu döndürür.
"""
import logging
import time
from dataclasses import dataclass

import requests
from config import Config

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DEMO_YANITI = (
    "Sistem demo modunda çalışıyor: API anahtarı tanımlı değil. Lütfen .env dosyanızı kontrol edin."
)


class AIServiceError(Exception):
    """Yapay zekâ servisine ulaşılamadığında fırlatılır; rotalar bunu JSON hataya çevirir.

    durum_kodu: kullanıcıya dönecek HTTP kodu (429 = kota doldu, 503 = servis kullanılamıyor)
    """

    def __init__(self, mesaj, durum_kodu=503, model=None, yedek_denenebilir=False):
        super().__init__(mesaj)
        self.durum_kodu = durum_kodu
        self.model = model
        # Kota dolu (429) veya model bulunamadı (404): başka bir modelle denemek anlamlı
        self.yedek_denenebilir = yedek_denenebilir


@dataclass
class YanitSonucu:
    cevap: str
    model: str
    prompt_token: int = 0
    cevap_token: int = 0
    sure_ms: int = 0
    demo: bool = False


class AIService:
    def yanit_uret(self, mesaj, gecmis, cekirdek, bilgi):
        """Sistem mesajını kurar, Groq'a sorar. Ana model kota verir veya erişilemezse bir kez yedek modelle dener."""
        if not Config.GROQ_API_KEY:
            log.warning("GROQ_API_KEY yok, demo modunda yanıt veriliyor.")
            return YanitSonucu(cevap=DEMO_YANITI, model="demo", demo=True)

        mesajlar = self.mesajlari_olustur(mesaj, gecmis, cekirdek, bilgi)
        try:
            return self._groq_cagir(Config.GROQ_MODEL, mesajlar)
        except AIServiceError as e:
            yedek = Config.GROQ_FALLBACK_MODEL
            # Groq'ta kota model başına ayrıdır; ana model dolduysa veya hesapta erişimi yoksa
            # yedek model hâlâ cevap verebilir
            if e.yedek_denenebilir and yedek and yedek != Config.GROQ_MODEL:
                log.warning("%s kullanılamadı, yedek model %s deneniyor.", Config.GROQ_MODEL, yedek)
                return self._groq_cagir(yedek, mesajlar)
            raise

    def mesajlari_olustur(self, mesaj, gecmis, cekirdek, bilgi):
        """Sıra önemli: sistem mesajı (çekirdek + bilgi belgesi), sonra geçmiş, en sonda yeni kullanıcı mesajı."""
        mesajlar = [{"role": "system", "content": f"{cekirdek}\n\n<bilgi>\n{bilgi}\n</bilgi>"}]
        mesajlar += self.gecmisi_temizle(gecmis)
        mesajlar.append({"role": "user", "content": mesaj})
        return mesajlar

    @staticmethod
    def gecmisi_temizle(gecmis):
        """Frontend'den gelen geçmişte sadece geçerli {role, content} kayıtlarını tutar.

        Token bütçesi için hem mesaj sayısı hem toplam karakter sınırlanır; en yeni mesajlar korunur.
        """
        if not isinstance(gecmis, list):
            return []
        temiz = [
            {"role": m["role"], "content": m["content"].strip()}
            for m in gecmis
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")    # "system" rolü dışarıdan kabul edilmez
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ][-Config.AI_HISTORY_MAX_MESSAGES:]

        secilen, toplam = [], 0
        for m in reversed(temiz):
            toplam += len(m["content"])
            if toplam > Config.AI_HISTORY_MAX_CHARS:
                break
            secilen.append(m)
        return list(reversed(secilen))

    @staticmethod
    def _groq_cagir(model, mesajlar):
        baslangic = time.monotonic()
        govde = {
            "model": model,
            "messages": mesajlar,
            "temperature": Config.AI_TEMPERATURE,
            "max_completion_tokens": Config.AI_MAX_TOKENS,
        }
        if Config.AI_REASONING_EFFORT:
            govde["reasoning_effort"] = Config.AI_REASONING_EFFORT
            govde["include_reasoning"] = False     # düşünme metni gereksiz yere geri gelmesin
        try:
            yanit = requests.post(
                GROQ_URL,
                json=govde,
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                timeout=Config.AI_TIMEOUT,
            )
        except requests.Timeout as e:
            log.error("Groq zaman aşımı (%s).", model)
            raise AIServiceError("Yapay zekâ servisi zamanında yanıt vermedi.", model=model) from e
        except requests.RequestException as e:
            log.error("Groq bağlantı hatası (%s): %s", model, e)
            raise AIServiceError("Yapay zekâ servisine bağlanılamadı.", model=model) from e

        if yanit.status_code == 429:
            log.warning("Groq kota sınırı (%s): %s", model, yanit.text[:200])
            raise AIServiceError(
                "Şu an çok yoğunuz, lütfen birkaç saniye sonra tekrar deneyin.", 429,
                model=model, yedek_denenebilir=True,
            )
        if yanit.status_code == 404:
            log.error("Groq modeli bulunamadı veya hesapta erişim yok (%s): %s", model, yanit.text[:200])
            raise AIServiceError(
                "Yapay zekâ servisi şu an kullanılamıyor.", model=model, yedek_denenebilir=True
            )
        if yanit.status_code == 401:
            log.critical("Groq API anahtarı geçersiz.")
            raise AIServiceError("Yapay zekâ servisi şu an kullanılamıyor.", model=model)
        if yanit.status_code != 200:
            log.error("Groq HTTP %s (%s): %s", yanit.status_code, model, yanit.text[:300])
            raise AIServiceError("Yapay zekâ servisi şu an yanıt veremiyor.", model=model)

        try:
            veri = yanit.json()
            secim = veri["choices"][0]
            cevap = (secim["message"]["content"] or "").strip()
        except (ValueError, KeyError, IndexError, TypeError) as e:
            log.error("Groq beklenmeyen yanıt biçimi (%s).", model)
            raise AIServiceError("Yapay zekâ servisi geçersiz yanıt döndürdü.", model=model) from e

        # Boş veya token sınırında yarım kalmış cevap kullanıcıya gösterilmez
        if not cevap or secim.get("finish_reason") == "length":
            log.error("Groq boş veya yarım cevap döndürdü (%s, finish_reason=%s).", model, secim.get("finish_reason"))
            raise AIServiceError("Yapay zekâ eksik bir yanıt üretti, lütfen tekrar deneyin.", model=model)

        kullanim = veri.get("usage") or {}
        return YanitSonucu(
            cevap=cevap,
            model=model,
            prompt_token=int(kullanim.get("prompt_tokens") or 0),
            cevap_token=int(kullanim.get("completion_tokens") or 0),
            sure_ms=int((time.monotonic() - baslangic) * 1000),
        )


# Tüm uygulamanın kullandığı tek örnek
ai_service = AIService()
