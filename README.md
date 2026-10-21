# OnBuddy Backend

Flask tabanlı İK chatbot ve yönetim paneli backend'i.

## Kurulum
```bash
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env       # macOS/Linux: cp .env.example .env
python run.py
```
- Chatbot: http://localhost:5000/
- Yönetim paneli: http://localhost:5000/panel
- Sağlık kontrolü: http://localhost:5000/health

## API
| Metot | Yol | Açıklama |
|---|---|---|
| POST | `/api/chat` | `{message, history}` → AI yanıtı |
| POST | `/api/candidates` | `{name, email, phone?, position?, message?}` kayıt |
| GET | `/api/candidates` | Kayıtları listeler (`ADMIN_TOKEN` varsa `X-Admin-Token` başlığı gerekir) |

## Deploy (Render)
Start command: `gunicorn run:app`
