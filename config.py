import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    DATABASE_URL = os.environ.get("DATABASE_URL", "onbuddy.db")
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
    CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    BUSINESS_CONTEXT = os.environ.get(
        "BUSINESS_CONTEXT",
        "Sen OnBuddy'nin İK asistanısın. Kısa, kibar ve profesyonel Türkçe yanıt ver.",
    )
