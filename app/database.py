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
    """'leads' tablosunu (yoksa) oluşturur. Uygulama açılırken bir kez çağrılır."""
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
