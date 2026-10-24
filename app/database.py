"""Veri katmanı: projedeki TÜM SQL yalnızca bu dosyada bulunur."""
import sqlite3
from flask import current_app


class VeritabaniHatasi(Exception):
    """Veritabanı işlemi başarısız olduğunda fırlatılır; rotalar bunu kibar bir JSON'a çevirir."""


def get_db():
    """Veritabanına bağlanır. row_factory sayesinde satir["isim"] gibi sütun adıyla erişilir."""
    baglanti = sqlite3.connect(current_app.config["DATABASE_URL"])
    baglanti.row_factory = sqlite3.Row
    return baglanti


def init_db(app):
    """Tabloları (yoksa) oluşturur. Uygulama açılırken bir kez çağrılır."""
    with app.app_context():
        baglanti = get_db()
        try:
            # eposta ve pozisyon, İK konusuna göre eklediğimiz isteğe bağlı sütunlar
            baglanti.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isim TEXT NOT NULL,
                    telefon TEXT NOT NULL,
                    eposta TEXT,
                    pozisyon TEXT,
                    mesaj TEXT,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Açık pozisyonlar: yapay zekânın kariyer sorularındaki bilgi kaynağı
            baglanti.execute(
                """
                CREATE TABLE IF NOT EXISTS pozisyonlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baslik TEXT NOT NULL,
                    departman TEXT,
                    lokasyon TEXT,
                    calisma_sekli TEXT,
                    aciklama TEXT,
                    aktif INTEGER NOT NULL DEFAULT 1,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # RAG bilgi parçaları (FTS5 tam metin araması).
            # Sadece "arama" sütunu indekslenir: Türkçe karakterleri sadeleştirilmiş metin.
            # Orijinal başlık ve içerik yapay zekâya gönderilmek için saklanır.
            baglanti.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS bilgi_parcalari USING fts5(
                    arama,
                    baslik UNINDEXED,
                    icerik UNINDEXED,
                    kategori UNINDEXED,
                    kaynak UNINDEXED,
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )
            # Hangi dokümanın hangi sürümünün indekslendiği (değişmeyen dosya yeniden indekslenmez)
            baglanti.execute(
                """
                CREATE TABLE IF NOT EXISTS bilgi_surumu (
                    kaynak TEXT PRIMARY KEY,
                    hash TEXT NOT NULL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Yapay zekâ kullanım kaydı. KVKK gereği mesaj içeriği TUTULMAZ, sadece sayılar.
            baglanti.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_kullanim (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model TEXT,
                    prompt_token INTEGER NOT NULL DEFAULT 0,
                    cevap_token INTEGER NOT NULL DEFAULT 0,
                    sure_ms INTEGER,
                    durum TEXT NOT NULL
                )
                """
            )
            baglanti.commit()
        finally:
            baglanti.close()


def lead_ekle(isim, telefon, mesaj="", eposta="", pozisyon=""):
    """Yeni bir aday kaydı ekler."""
    baglanti = get_db()
    try:
        # Değerler SQL metnine yapıştırılmaz; ? yer tutucularıyla ayrı gönderilir (SQL Injection koruması)
        baglanti.execute(
            "INSERT INTO leads (isim, telefon, eposta, pozisyon, mesaj) VALUES (?, ?, ?, ?, ?)",
            (isim, telefon, eposta, pozisyon, mesaj),
        )
        baglanti.commit()
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Kayıt veritabanına eklenemedi.") from e
    finally:
        baglanti.close()


def tum_leadler():
    """Tüm kayıtları en yeniden eskiye doğru, sözlük listesi olarak döndürür."""
    baglanti = get_db()
    try:
        satirlar = baglanti.execute("SELECT * FROM leads ORDER BY tarih DESC, id DESC").fetchall()
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Kayıtlar okunamadı.") from e
    finally:
        baglanti.close()
    return [dict(satir) for satir in satirlar]


# ── Pozisyonlar ───────────────────────────────────────
def pozisyon_sayisi():
    baglanti = get_db()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM pozisyonlar").fetchone()[0]
    finally:
        baglanti.close()


def pozisyon_ekle(baslik, departman="", lokasyon="", calisma_sekli="", aciklama="", aktif=True):
    """Yeni pozisyon ekler ve id'sini döndürür."""
    baglanti = get_db()
    try:
        imlec = baglanti.execute(
            "INSERT INTO pozisyonlar (baslik, departman, lokasyon, calisma_sekli, aciklama, aktif) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (baslik, departman, lokasyon, calisma_sekli, aciklama, 1 if aktif else 0),
        )
        baglanti.commit()
        return imlec.lastrowid
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Pozisyon eklenemedi.") from e
    finally:
        baglanti.close()


def pozisyon_aktifligi_degistir(pozisyon_id, aktif):
    baglanti = get_db()
    try:
        baglanti.execute(
            "UPDATE pozisyonlar SET aktif = ? WHERE id = ?", (1 if aktif else 0, pozisyon_id)
        )
        baglanti.commit()
    finally:
        baglanti.close()


def aktif_pozisyonlar():
    """Yayındaki pozisyonları en yeniden eskiye döndürür."""
    baglanti = get_db()
    try:
        satirlar = baglanti.execute(
            "SELECT id, baslik, departman, lokasyon, calisma_sekli, aciklama "
            "FROM pozisyonlar WHERE aktif = 1 ORDER BY tarih DESC, id DESC"
        ).fetchall()
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Pozisyonlar okunamadı.") from e
    finally:
        baglanti.close()
    return [dict(satir) for satir in satirlar]


# ── RAG bilgi parçaları ───────────────────────────────
def bilgi_surumu(kaynak):
    """Kaynağın en son indekslenen hash'ini döndürür (hiç indekslenmediyse None)."""
    baglanti = get_db()
    try:
        satir = baglanti.execute(
            "SELECT hash FROM bilgi_surumu WHERE kaynak = ?", (kaynak,)
        ).fetchone()
    finally:
        baglanti.close()
    return satir["hash"] if satir else None


def bilgi_kaynaklari():
    """İndekslenmiş tüm kaynak adlarını döndürür."""
    baglanti = get_db()
    try:
        return [s["kaynak"] for s in baglanti.execute("SELECT kaynak FROM bilgi_surumu")]
    finally:
        baglanti.close()


def bilgi_parcalarini_yenile(kaynak, hash_degeri, parcalar):
    """Bir kaynağın eski parçalarını silip yenilerini yazar; tek işlemde (ya hepsi ya hiçbiri).

    parcalar: [{"arama", "baslik", "icerik", "kategori"}]
    """
    baglanti = get_db()
    try:
        with baglanti:
            baglanti.execute("DELETE FROM bilgi_parcalari WHERE kaynak = ?", (kaynak,))
            baglanti.executemany(
                "INSERT INTO bilgi_parcalari (arama, baslik, icerik, kategori, kaynak) "
                "VALUES (?, ?, ?, ?, ?)",
                [(p["arama"], p["baslik"], p["icerik"], p["kategori"], kaynak) for p in parcalar],
            )
            baglanti.execute(
                "INSERT INTO bilgi_surumu (kaynak, hash) VALUES (?, ?) "
                "ON CONFLICT(kaynak) DO UPDATE SET hash = excluded.hash, tarih = CURRENT_TIMESTAMP",
                (kaynak, hash_degeri),
            )
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Bilgi parçaları güncellenemedi.") from e
    finally:
        baglanti.close()


def bilgi_kaynagini_sil(kaynak):
    """Artık var olmayan bir dokümanın parçalarını ve sürüm kaydını siler."""
    baglanti = get_db()
    try:
        with baglanti:
            baglanti.execute("DELETE FROM bilgi_parcalari WHERE kaynak = ?", (kaynak,))
            baglanti.execute("DELETE FROM bilgi_surumu WHERE kaynak = ?", (kaynak,))
    finally:
        baglanti.close()


def bilgi_ara(fts_sorgusu, limit):
    """FTS5 ile arar; en alakalı parçalar önce gelir (bm25 puanı küçük = daha alakalı)."""
    baglanti = get_db()
    try:
        satirlar = baglanti.execute(
            "SELECT baslik, icerik, kategori, kaynak FROM bilgi_parcalari "
            "WHERE bilgi_parcalari MATCH ? ORDER BY bm25(bilgi_parcalari) LIMIT ?",
            (fts_sorgusu, limit),
        ).fetchall()
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Bilgi araması yapılamadı.") from e
    finally:
        baglanti.close()
    return [dict(satir) for satir in satirlar]


# ── Yapay zekâ kullanım kaydı ─────────────────────────
def ai_kullanim_ekle(model, prompt_token, cevap_token, sure_ms, durum):
    baglanti = get_db()
    try:
        baglanti.execute(
            "INSERT INTO ai_kullanim (model, prompt_token, cevap_token, sure_ms, durum) "
            "VALUES (?, ?, ?, ?, ?)",
            (model, prompt_token, cevap_token, sure_ms, durum),
        )
        baglanti.commit()
    except sqlite3.Error as e:
        raise VeritabaniHatasi("Kullanım kaydı yazılamadı.") from e
    finally:
        baglanti.close()


def bugunku_token_toplami():
    """Bugün (UTC) harcanan toplam token sayısı."""
    baglanti = get_db()
    try:
        satir = baglanti.execute(
            "SELECT COALESCE(SUM(prompt_token + cevap_token), 0) FROM ai_kullanim "
            "WHERE date(tarih) = date('now')"
        ).fetchone()
    finally:
        baglanti.close()
    return satir[0]
