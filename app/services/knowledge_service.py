"""Bilgi katmanı: yapay zekânın okuyacağı tek dosyayı yönetir.

- knowledge/asistan.md : kurallar, üslup ve bilgi (<bilgi> bölümü) tek belgede; sistem mesajının tamamıdır.
  Parçalanmaz, her soruda eksiksiz modele gönderilir.

Arama, parçalama veya veritabanı yoktur. Dosya değişince (mtime) bir sonraki istekte yeniden okunur.
"""
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

ASISTAN_DOSYASI = "asistan.md"
# Asistan belgesi bu uzunluğu aşarsa uyarı yazılır: her soruda gönderildiği için token bütçesini ve
# Groq'un dakikalık sınırını hızla tüketir (yaklaşık 3 karakter = 1 token).
BILGI_UYARI_KARAKTER = 15000


class BilgiHatasi(Exception):
    """Zorunlu bir bilgi dosyası yok veya boş."""


def temizle(metin):
    """Yorum satırlarını (<!-- ... -->) atar; düzenleyen kişiye notlar modele gitmesin."""
    metin = re.sub(r"<!--.*?-->", "", metin, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", metin).strip()


class BilgiServisi:
    def __init__(self):
        self._onbellek = {}     # yol -> (mtime, metin)

    def _oku(self, yol):
        yol = Path(yol)
        try:
            mtime = yol.stat().st_mtime_ns
        except FileNotFoundError:
            raise BilgiHatasi(f"Bilgi dosyası bulunamadı: {yol}") from None
        kayit = self._onbellek.get(yol)
        if kayit and kayit[0] == mtime:
            return kayit[1]
        metin = temizle(yol.read_text(encoding="utf-8"))
        if not metin:
            raise BilgiHatasi(f"Bilgi dosyası boş: {yol}")
        self._onbellek[yol] = (mtime, metin)
        return metin

    def belge(self, app_config):
        """Asistan belgesinin tamamı: kurallar + bilgi (yorum satırları çıkarılmış)."""
        return self._oku(Path(app_config["KNOWLEDGE_DIR"]) / ASISTAN_DOSYASI)

    def dogrula(self, app_config):
        """Uygulama açılırken çağrılır: dosya yoksa açılış başarısız olur, soru anında cevapsız kalmaz."""
        uzunluk = len(self.belge(app_config))
        if uzunluk > BILGI_UYARI_KARAKTER:
            log.warning(
                "asistan.md %d karakter (yaklaşık %d token); her soruda gönderildiği için uzun. "
                "Token bütçesi ve Groq dakika sınırı için kısaltmayı düşünün.",
                uzunluk, uzunluk // 3,
            )
        return uzunluk


# Tüm uygulamanın kullandığı tek örnek
bilgi_servisi = BilgiServisi()
