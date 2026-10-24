"""RAG bilgi katmanı: dokümanları parçalar, SQLite FTS5'e indeksler ve soruya uygun parçaları bulur.

SQL burada yoktur; veritabanı işleri database.py fonksiyonlarıyla yapılır.
"""
import hashlib
import json
import logging
import re
from pathlib import Path

from app import database

log = logging.getLogger(__name__)

CEKIRDEK_DOSYASI = "cekirdek.md"            # sistem mesajı; indekslenmez, her istekte eklenir
ORNEK_POZISYON_DOSYASI = "ornek_pozisyonlar.json"
POZISYON_KAYNAGI = "pozisyonlar"            # tüm aktif pozisyonlar tek kaynak adı altında tutulur
KOK_UZUNLUGU = 5                            # Türkçe ekler için kelimenin ilk 5 harfiyle önek araması
MAKS_SORGU_KELIMESI = 12

# Aramada anlam taşımayan kelimeler (sadeleştirilmiş hâlleriyle)
DOLGU_KELIMELERI = frozenset(
    """
    acaba ama ancak bana beni benim bir biraz bize bizi bizim bu bunu bunun cok daha diye
    gibi hangi hem hep her ile icin iste kadar kim lazim nasil ne neden nedir nerede niye
    olan olarak olur sadece sen seni senin siz size sizi sizin sey simdi soyle su sunu var
    veya yani yok zaten merhaba selam lutfen tesekkur tesekkurler misiniz musunuz mudur midir
    neler nelerdir miyiz musun misin istiyorum istiyoruz isterim olabilir mumkun hakkinda
    """.split()
)

_TURKCE_SADE = str.maketrans("ıçğöşüâîû", "icgosuaiu")


def sadelestir(metin):
    """Türkçe'ye uygun küçük harf + aksan temizliği. İndekslerken ve ararken AYNI fonksiyon kullanılır.

    Python'un lower()'ı "İ" harfini "i̇" (noktalı) yapar ve "I"yı "i" sanar; bu yüzden önce elle çevrilir.
    """
    metin = metin.replace("İ", "i").replace("I", "ı").lower()
    return metin.translate(_TURKCE_SADE)


def dokumani_parcala(metin, kategori, maks_karakter):
    """Markdown'ı "## " başlıklarından böler. Uzun bölümler paragraf sınırından ikiye ayrılır.

    Her parçanın başlığı "Doküman › Bölüm" biçimindedir; parça tek başına okunsa da anlaşılır.
    """
    metin = re.sub(r"<!--.*?-->", "", metin, flags=re.S)   # yorum satırları (ör. MOCK notu) indekslenmez
    dokuman_basligi = ""
    bolumler = []           # [(bölüm başlığı, [satırlar])]
    for satir in metin.splitlines():
        if satir.startswith("# "):
            dokuman_basligi = satir[2:].strip()
        elif satir.startswith("## "):
            bolumler.append((satir[3:].strip(), []))
        elif bolumler:
            bolumler[-1][1].append(satir)

    parcalar = []
    for bolum_basligi, satirlar in bolumler:
        baslik = f"{dokuman_basligi} › {bolum_basligi}" if dokuman_basligi else bolum_basligi
        for icerik in _uzun_bolumu_bol("\n".join(satirlar).strip(), maks_karakter):
            parcalar.append(_parca(baslik, icerik, kategori))
    return parcalar


def _uzun_bolumu_bol(icerik, maks_karakter):
    """Bölüm sınırı aşıyorsa paragrafları sırayla toplayıp sınır içinde kalan parçalar üretir."""
    if not icerik:
        return []
    if len(icerik) <= maks_karakter:
        return [icerik]
    parcalar, gecerli = [], ""
    for paragraf in re.split(r"\n\s*\n", icerik):
        aday = f"{gecerli}\n\n{paragraf}".strip()
        if gecerli and len(aday) > maks_karakter:
            parcalar.append(gecerli)
            gecerli = paragraf
        else:
            gecerli = aday
    if gecerli:
        parcalar.append(gecerli)
    return parcalar


def _parca(baslik, icerik, kategori):
    return {"arama": sadelestir(f"{baslik}\n{icerik}"), "baslik": baslik, "icerik": icerik, "kategori": kategori}


def pozisyon_parcasi(pozisyon):
    """Bir pozisyon kaydını yapay zekânın okuyacağı tek bir bilgi parçasına çevirir."""
    alanlar = [
        ("Departman", pozisyon.get("departman")),
        ("Lokasyon", pozisyon.get("lokasyon")),
        ("Çalışma şekli", pozisyon.get("calisma_sekli")),
        ("Açıklama", pozisyon.get("aciklama")),
    ]
    icerik = "\n".join(f"{ad}: {deger}" for ad, deger in alanlar if deger)
    return _parca(f"Açık pozisyon › {pozisyon['baslik']}", icerik, "pozisyon")


def pozisyon_listesi_parcasi(pozisyonlar):
    """Tüm aktif pozisyonların kısa listesi. "Açık pozisyonlar neler?" sorusunda hepsi tek parçada gelsin
    diye var; ayrıntılar pozisyon başına ayrı parçalardadır."""
    if pozisyonlar:
        satirlar = [
            "- " + " / ".join(d for d in (p["baslik"], p.get("departman"), p.get("lokasyon"), p.get("calisma_sekli")) if d)
            for p in pozisyonlar
        ]
        icerik = "Şu anda açık olan pozisyonlar:\n" + "\n".join(satirlar)
    else:
        icerik = "Şu anda açık pozisyon bulunmuyor; genel başvuru yapılabilir."
    parca = _parca("Açık pozisyonlar listesi", icerik, "pozisyon")
    # Genel "ilan / iş / kariyer" sorularında bu liste öne çıksın
    parca["arama"] += "\nacik pozisyonlar is ilanlari kariyer firsatlari basvuru alim eleman"
    return parca


def fts_sorgusu_olustur(*metinler):
    """Sorudaki anlamlı kelimelerden FTS5 sorgusu üretir: "pozis"* OR "uzakt"* ...

    Türkçe'de ek çok olduğu için kelimenin ilk 5 harfiyle önek araması yapılır;
    böylece "pozisyonlarınız" sorusu "pozisyon" geçen parçayı bulur.
    Anlamlı kelime yoksa None döner (ör. sadece "merhaba").
    """
    kokler = []
    for metin in metinler:
        for kelime in re.findall(r"\w+", sadelestir(metin or "")):
            if len(kelime) < 3 or kelime.isdigit() or kelime in DOLGU_KELIMELERI:
                continue
            kok = kelime[:KOK_UZUNLUGU]
            if kok not in kokler:
                kokler.append(kok)
    if not kokler:
        return None
    # Kelimeler \w+ ile alındığı için tırnak içinde güvenle kullanılabilir (FTS sözdizimi enjekte edilemez)
    return " OR ".join(f'"{kok}"*' for kok in kokler[:MAKS_SORGU_KELIMESI])


def _hash(metin):
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


class BilgiServisi:
    def __init__(self):
        self._cekirdek = None

    def cekirdek(self, app_config):
        """Sistem mesajının sabit kısmı (knowledge/cekirdek.md). Bir kez okunur, bellekte tutulur."""
        if self._cekirdek is None:
            yol = Path(app_config["KNOWLEDGE_DIR"]) / CEKIRDEK_DOSYASI
            self._cekirdek = yol.read_text(encoding="utf-8").strip()
        return self._cekirdek

    def indeksle(self, app_config):
        """Uygulama açılırken çağrılır: değişen dokümanları ve pozisyonları yeniden indeksler."""
        klasor = Path(app_config["KNOWLEDGE_DIR"])
        maks = app_config["RAG_MAX_CHUNK_CHARS"]
        mevcut_kaynaklar = set()

        for dosya in sorted(klasor.glob("*.md")):
            if dosya.name == CEKIRDEK_DOSYASI:
                continue
            kaynak = dosya.name
            mevcut_kaynaklar.add(kaynak)
            metin = dosya.read_text(encoding="utf-8")
            # Ayar değişince de yeniden parçalansın diye hash'e parça sınırı da katılır
            hash_degeri = _hash(f"{maks}\n{metin}")
            if database.bilgi_surumu(kaynak) == hash_degeri:
                continue
            parcalar = dokumani_parcala(metin, dosya.stem, maks)
            database.bilgi_parcalarini_yenile(kaynak, hash_degeri, parcalar)
            log.info("Bilgi dokümanı indekslendi: %s (%d parça)", kaynak, len(parcalar))

        # Klasörden silinen dokümanların parçaları da temizlenir
        for kaynak in database.bilgi_kaynaklari():
            if kaynak.endswith(".md") and kaynak not in mevcut_kaynaklar:
                database.bilgi_kaynagini_sil(kaynak)

        if app_config["ORNEK_POZISYONLARI_YUKLE"] and database.pozisyon_sayisi() == 0:
            self._ornek_pozisyonlari_yukle(klasor / ORNEK_POZISYON_DOSYASI)
        self.pozisyonlari_indeksle()

    @staticmethod
    def _ornek_pozisyonlari_yukle(dosya):
        """Şimdilik gerçek ilan olmadığı için mock pozisyonlarla başlanır."""
        if not dosya.exists():
            return
        for p in json.loads(dosya.read_text(encoding="utf-8")):
            database.pozisyon_ekle(
                p["baslik"], p.get("departman", ""), p.get("lokasyon", ""),
                p.get("calisma_sekli", ""), p.get("aciklama", ""),
            )
        log.info("Örnek (mock) pozisyonlar yüklendi.")

    @staticmethod
    def pozisyonlari_indeksle():
        """Aktif pozisyonları arama tablosuna yazar. Pozisyon eklenince/değişince de çağrılmalıdır."""
        pozisyonlar = database.aktif_pozisyonlar()
        # Liste parçası pozisyon yokken de yazılır; model "açık pozisyon yok" bilgisini görsün, uydurmasın
        parcalar = [pozisyon_listesi_parcasi(pozisyonlar)] + [pozisyon_parcasi(p) for p in pozisyonlar]
        hash_degeri = _hash(json.dumps(pozisyonlar, ensure_ascii=False, sort_keys=True, default=str))
        if database.bilgi_surumu(POZISYON_KAYNAGI) != hash_degeri:
            database.bilgi_parcalarini_yenile(POZISYON_KAYNAGI, hash_degeri, parcalar)

    @staticmethod
    def ara(soru, onceki_soru, limit):
        """Soruya en uygun parçaları döndürür. Önceki kullanıcı sorusu devam sorularını anlamak için eklenir
        (ör. "peki uzaktan çalışma var mı?")."""
        sorgu = fts_sorgusu_olustur(soru, onceki_soru)
        if sorgu is None:
            return []
        return database.bilgi_ara(sorgu, limit)


# Tüm uygulamanın kullandığı tek örnek
bilgi_servisi = BilgiServisi()
