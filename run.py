import os
from app import create_app

# Uygulamayı fabrikadan al. Render'da gunicorn bu "app" değişkenini kullanır: gunicorn run:app
app = create_app()

if __name__ == "__main__":
    # Sadece "python run.py" ile çalıştırınca devreye girer (yerel geliştirme)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
