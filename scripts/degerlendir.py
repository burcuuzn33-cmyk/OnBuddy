"""Gerçek Groq ile 25 soruluk değerlendirme. Elle çalıştırılır, cevaplar gözle kontrol edilir.

Kullanım (proje klasöründen, .env'de GROQ_API_KEY dolu olmalı):
    python -m scripts.degerlendir

Her soru ayrı bir sohbettir (geçmiş gönderilmez). Groq'un dakikalık sınırına takılmamak için
sorular arasında bekler. Kullanım kayıtları geçici bir veritabanına yazılır, onbuddy.db'ye dokunulmaz.
"""
import json
import tempfile
import time
from pathlib import Path

from app import create_app
from config import Config

BEKLEME_SANIYE = 4


def main():
    if not Config.GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY tanımlı değil (.env dosyasını kontrol edin).")

    sorular = json.loads((Path(__file__).parent / "degerlendirme_sorulari.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as klasor:
        app = create_app("development", {
            "DATABASE_URL": str(Path(klasor) / "degerlendirme.db"),
            "CHAT_RATE_LIMIT_REQUESTS": 1000,
        })
        client = app.test_client()
        form_uyumu = 0
        for i, s in enumerate(sorular, 1):
            yanit = client.post("/api/sohbet", json={"mesaj": s["soru"]}).get_json()
            form = yanit.get("yonlendirme")
            form_uyumu += form == s["form"]
            print(f"\n[{i}/{len(sorular)}] ({s['tur']}) {s['soru']}")
            print(f"  Beklenen : {s['beklenen']}  | form: {s['form']}")
            print(f"  Cevap    : {yanit.get('cevap') or yanit.get('hata')}")
            print(f"  Form     : {form} {'✓' if form == s['form'] else '✗'}")
            time.sleep(BEKLEME_SANIYE)
        print(f"\nForm yönlendirmesi uyumu: {form_uyumu}/{len(sorular)}")
        print("Cevapların doğruluğunu 'Beklenen' satırlarıyla karşılaştırarak gözle kontrol edin.")


if __name__ == "__main__":
    main()
