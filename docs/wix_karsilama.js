/**
 * Wix Velo — Karşılama Sayfası (B2C): AI sohbet + iletişim formu
 * Wix Studio'da sayfayı aç → Kod paneli (Velo) → bu kodu sayfa koduna yapıştır.
 *
 * Bileşenlere Wix'te şu ID'leri ver (Özellikler paneli → ID):
 *   #inputMesaj    Metin kutusu  — ziyaretçinin sorusu
 *   #btnSor        Buton         — "Sor"
 *   #txtCevap      Metin         — AI yanıtı
 *   #inputIsim     Metin kutusu  — Ad Soyad (zorunlu)
 *   #inputTelefon  Metin kutusu  — Telefon (zorunlu)
 *   #inputEposta   Metin kutusu  — E-posta (isteğe bağlı)
 *   #inputPozisyon Metin kutusu  — İlgilenilen pozisyon (isteğe bağlı)
 *   #btnKaydet     Buton         — "Kaydet"
 *   #txtDurum      Metin         — durum / hata mesajları
 *
 * UX: Z-Pattern — logo sol üst, sohbet kartı sağda (Glassmorphism: kutu şeffaflığı + blur), form altta.
 */
import { fetch } from 'wix-fetch';

// Render'a yükledikten sonra kendi adresinle değiştir (sonunda / olmadan)
const API = 'https://ONBUDDY-APP-ADIN.onrender.com';

let gecmis = []; // çok turlu sohbet için {role, content} listesi

$w.onReady(function () {
    $w('#btnSor').onClick(sohbetGonder);
    $w('#btnKaydet').onClick(leadKaydet);
    $w('#inputMesaj').onKeyPress((event) => {
        if (event.key === 'Enter') sohbetGonder();
    });
});

// POST /api/sohbet  gönderilen: {mesaj, gecmis}  dönen: {basari, cevap | hata}
async function sohbetGonder() {
    const mesaj = $w('#inputMesaj').value.trim();
    if (!mesaj) return;

    $w('#btnSor').disable();
    $w('#txtCevap').text = 'Yanıt hazırlanıyor...';
    try {
        const yanit = await fetch(`${API}/api/sohbet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mesaj, gecmis })
        });
        const veri = await yanit.json();

        if (veri.basari) {
            $w('#txtCevap').text = veri.cevap;
            $w('#inputMesaj').value = '';
            gecmis.push({ role: 'user', content: mesaj });
            gecmis.push({ role: 'assistant', content: veri.cevap });
            gecmis = gecmis.slice(-10); // token limitini aşmamak için son 10 mesaj
        } else {
            $w('#txtCevap').text = veri.hata || 'Bir hata oluştu.';
        }
    } catch (hata) {
        console.error('Sohbet hatası:', hata);
        $w('#txtCevap').text = 'Sunucuya ulaşılamadı. Lütfen tekrar deneyin.';
    } finally {
        $w('#btnSor').enable();
    }
}

// POST /api/leads  gönderilen: {isim, telefon, eposta, pozisyon, mesaj}  dönen: {basari, mesaj | hata}
async function leadKaydet() {
    const isim = $w('#inputIsim').value.trim();
    const telefon = $w('#inputTelefon').value.trim();
    if (!isim || !telefon) {
        $w('#txtDurum').text = 'Lütfen ad soyad ve telefon alanlarını doldurun.';
        return;
    }

    $w('#btnKaydet').disable();
    $w('#txtDurum').text = 'Kaydediliyor...';
    try {
        const yanit = await fetch(`${API}/api/leads`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                isim,
                telefon,
                eposta: $w('#inputEposta').value.trim(),
                pozisyon: $w('#inputPozisyon').value.trim(),
                mesaj: $w('#inputMesaj').value.trim()
            })
        });
        const veri = await yanit.json();

        if (veri.basari) {
            $w('#txtDurum').text = '✓ ' + veri.mesaj;
            $w('#inputIsim').value = '';
            $w('#inputTelefon').value = '';
            $w('#inputEposta').value = '';
            $w('#inputPozisyon').value = '';
        } else {
            $w('#txtDurum').text = veri.hata || 'Kayıt sırasında hata oluştu.';
        }
    } catch (hata) {
        console.error('Kayıt hatası:', hata);
        $w('#txtDurum').text = 'Sunucuya ulaşılamadı. Lütfen tekrar deneyin.';
    } finally {
        $w('#btnKaydet').enable();
    }
}
