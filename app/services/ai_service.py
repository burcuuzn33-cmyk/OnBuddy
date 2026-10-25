"""Yapay zekâ servis katmanı: tüm Groq ve Gemini API çağrıları yalnızca bu dosyada bulunur.

Bu dosya Flask, HTTP rotaları veya veritabanı hakkında hiçbir şey bilmez;
asistan belgesini (kurallar + bilgi) ve geçmişi alır, sağlayıcıları sırayla dener ve sonucu döndürür.
"""
import logging
import time
from dataclasses import dataclass, field

import requests
from config import Config

log = logging.getLogger(__name__)

# İkisi de OpenAI uyumlu "chat/completions" biçimini konuşur; fark yalnızca adres, anahtar ve model.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

DEMO_YANITI = (
    "Sistem demo modunda çalışıyor: API anahtarı tanımlı değil. Lütfen .env dosyanızı kontrol edin."
)


class AIServiceError(Exception):
    """Hiçbir sağlayıcıdan cevap alınamadığında fırlatılır; rotalar bunu JSON hataya çevirir.

    durum_kodu: kullanıcıya dönecek HTTP kodu (429 = kota doldu, 503 = servis kullanılamıyor)
    denemeler: başarısız olan her sağlayıcı denemesi (kullanım kaydı için); tek denemede kendisidir
    """

    def __init__(self, mesaj, durum_kodu=503, model=None):
        super().__init__(mesaj)
        self.durum_kodu = durum_kodu
        self.model = model
        self.denemeler = [self]


@dataclass
class YanitSonucu:
    cevap: str
    model: str
    prompt_token: int = 0
    cevap_token: int = 0
    sure_ms: int = 0
    demo: bool = False
    # Bu cevaptan önce başarısız olan sağlayıcı denemeleri (ör. Groq kotası doldu, cevap Gemini'den geldi)
    basarisiz: list = field(default_factory=list)


@dataclass(frozen=True)
class Saglayici:
    ad: str
    url: str
    anahtar: str
    model: str


class AIService:
    def saglayicilar(self):
        """AI_PROVIDER_ORDER sırasına göre, anahtarı tanımlı sağlayıcılar."""
        tanimli = {
            "groq": Saglayici("groq", GROQ_URL, Config.GROQ_API_KEY, Config.GROQ_MODEL),
            "gemini": Saglayici("gemini", GEMINI_URL, Config.GEMINI_API_KEY, Config.GEMINI_MODEL),
        }
        sira = []
        for ad in Config.AI_PROVIDER_ORDER:
            s = tanimli.get(ad)
            if s and s.anahtar and s.model and s not in sira:
                sira.append(s)
        return sira

    def yanit_uret(self, mesaj, gecmis, belge):
        """Asistan belgesiyle mesajları kurar; sağlayıcıları sırayla dener, ilk geçerli cevabı döndürür.

        Bir sağlayıcıdan geçerli cevap alınamazsa (kota, zaman aşımı, sunucu hatası, boş cevap...) sıradakine
        geçilir. Tüm denemeler AI_TOTAL_TIMEOUT içinde kalır; süre dolduysa sıradaki denenmez.
        """
        zincir = self.saglayicilar()
        if not zincir:
            log.warning("Yapay zekâ API anahtarı yok, demo modunda yanıt veriliyor.")
            return YanitSonucu(cevap=DEMO_YANITI, model="demo", demo=True)

        mesajlar = self.mesajlari_olustur(mesaj, gecmis, belge)
        baslangic = time.monotonic()
        denemeler = []
        for s in zincir:
            kalan = Config.AI_TOTAL_TIMEOUT - (time.monotonic() - baslangic)
            if denemeler and kalan < 1:
                log.warning("Toplam süre doldu, %s denenmedi.", s.ad)
                break
            try:
                sonuc = self._cagir(s, mesajlar, min(Config.AI_TIMEOUT, kalan))
            except AIServiceError as e:
                denemeler.append(e)
                if s is not zincir[-1]:
                    log.warning("%s (%s) kullanılamadı, sıradaki sağlayıcı deneniyor.", s.ad, s.model)
                continue
            sonuc.basarisiz = denemeler
            return sonuc

        # Hepsi başarısız: hepsi kota hatasıysa 429, aksi halde asıl sorunu anlatan son hata (503) döner
        hata = next((e for e in reversed(denemeler) if e.durum_kodu != 429), denemeler[-1])
        hata.denemeler = denemeler
        raise hata

    def mesajlari_olustur(self, mesaj, gecmis, belge):
        """Sıra önemli: sistem mesajı (asistan belgesi), sonra geçmiş, en sonda yeni kullanıcı mesajı."""
        mesajlar = [{"role": "system", "content": belge}]
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
    def _cagir(saglayici, mesajlar, zaman_asimi):
        ad, model = saglayici.ad, saglayici.model
        baslangic = time.monotonic()
        govde = {
            "model": model,
            "messages": mesajlar,
            "temperature": Config.AI_TEMPERATURE,
            "max_completion_tokens": Config.AI_MAX_TOKENS,
        }
        if Config.AI_REASONING_EFFORT:
            govde["reasoning_effort"] = Config.AI_REASONING_EFFORT
            if ad == "groq":
                govde["include_reasoning"] = False     # düşünme metni gereksiz yere geri gelmesin
        try:
            yanit = requests.post(
                saglayici.url,
                json=govde,
                headers={"Authorization": f"Bearer {saglayici.anahtar}"},   # anahtar adrese yazılmaz, loga düşmez
                timeout=zaman_asimi,
            )
        except requests.Timeout as e:
            log.error("%s zaman aşımı (%s).", ad, model)
            raise AIServiceError("Yapay zekâ servisi zamanında yanıt vermedi.", model=model) from e
        except requests.RequestException as e:
            log.error("%s bağlantı hatası (%s): %s", ad, model, e)
            raise AIServiceError("Yapay zekâ servisine bağlanılamadı.", model=model) from e

        if yanit.status_code == 429:
            log.warning("%s kota sınırı (%s): %s", ad, model, yanit.text[:200])
            raise AIServiceError(
                "Şu an çok yoğunuz, lütfen birkaç saniye sonra tekrar deneyin.", 429, model=model
            )
        if yanit.status_code == 404:
            log.error("%s modeli bulunamadı veya erişim yok (%s): %s", ad, model, yanit.text[:200])
            raise AIServiceError("Yapay zekâ servisi şu an kullanılamıyor.", model=model)
        if yanit.status_code in (401, 403):
            log.critical("%s API anahtarı geçersiz veya yetkisiz (HTTP %s).", ad, yanit.status_code)
            raise AIServiceError("Yapay zekâ servisi şu an kullanılamıyor.", model=model)
        if yanit.status_code != 200:
            log.error("%s HTTP %s (%s): %s", ad, yanit.status_code, model, yanit.text[:300])
            raise AIServiceError("Yapay zekâ servisi şu an yanıt veremiyor.", model=model)

        try:
            veri = yanit.json()
            secim = veri["choices"][0]
            cevap = (secim["message"]["content"] or "").strip()
        except (ValueError, KeyError, IndexError, TypeError) as e:
            log.error("%s beklenmeyen yanıt biçimi (%s).", ad, model)
            raise AIServiceError("Yapay zekâ servisi geçersiz yanıt döndürdü.", model=model) from e

        # Boş veya token sınırında yarım kalmış cevap kullanıcıya gösterilmez
        if not cevap or secim.get("finish_reason") == "length":
            log.error("%s boş veya yarım cevap döndürdü (%s, finish_reason=%s).", ad, model, secim.get("finish_reason"))
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
