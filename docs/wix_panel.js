/**
 * Wix Velo — Yönetim Paneli (B2B): adayları Repeater ile tablo gibi gösterir
 * Wix Studio'da panel sayfasını aç → Kod paneli (Velo) → bu kodu sayfa koduna yapıştır.
 * Bu sayfayı Wix'te sadece üyelere/yöneticiye açık yap (Sayfa ayarları → İzinler).
 *
 * Bileşen ID'leri:
 *   #repeaterLeads  Repeater — her satır bir aday
 *     Repeater'ın İÇİNDE: #txtIsim, #txtTelefon, #txtEposta, #txtPozisyon, #txtMesaj, #txtTarih
 *   #txtToplam      Metin — toplam aday sayısı
 *   #btnYenile      Buton — listeyi yeniden yükler
 *
 * UX: F-Pattern — en önemli kolon (isim) en solda.
 */
import { fetch } from 'wix-fetch';

// Render'a yükledikten sonra kendi adresinle değiştir (sonunda / olmadan)
const API = 'https://ONBUDDY-APP-ADIN.onrender.com';

$w.onReady(async function () {
    // onItemReady bir kez tanımlanır; her satır oluşturulurken çalışır.
    // Satır içindeki bileşenlere $item ile erişilir — $w ile DEĞİL (yoksa tüm satırlar aynı olur).
    $w('#repeaterLeads').onItemReady(($item, satir) => {
        $item('#txtIsim').text = satir.isim;
        $item('#txtTelefon').text = satir.telefon;
        $item('#txtEposta').text = satir.eposta || '—';
        $item('#txtPozisyon').text = satir.pozisyon || '—';
        $item('#txtMesaj').text = satir.mesaj || '—';
        $item('#txtTarih').text = satir.tarih;
    });

    $w('#btnYenile').onClick(leadleriYukle);
    await leadleriYukle();
});

// GET /api/leads  dönen: {basari, toplam, leadler: [{id, isim, telefon, eposta, pozisyon, mesaj, tarih}]}
async function leadleriYukle() {
    $w('#txtToplam').text = 'Yükleniyor...';
    try {
        const yanit = await fetch(`${API}/api/leads`, { method: 'GET' });
        const veri = await yanit.json();
        if (!veri.basari) throw new Error(veri.hata || 'Veri alınamadı');

        // Repeater her objede benzersiz bir _id (metin) ister
        $w('#repeaterLeads').data = veri.leadler.map((l) => ({
            _id: String(l.id),
            isim: l.isim,
            telefon: l.telefon,
            eposta: l.eposta,
            pozisyon: l.pozisyon,
            mesaj: l.mesaj,
            tarih: tarihYaz(l.tarih)
        }));
        $w('#txtToplam').text = `Toplam: ${veri.toplam} aday`;
    } catch (hata) {
        console.error('Liste yüklenemedi:', hata);
        $w('#txtToplam').text = 'Liste yüklenemedi: ' + hata.message;
    }
}

// SQLite tarihi UTC "2026-10-22 10:30:00" biçimindedir → "22.10.2026 13:30"
function tarihYaz(metin) {
    if (!metin) return '—';
    const tarih = new Date(metin.replace(' ', 'T') + 'Z');
    return tarih.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
}
