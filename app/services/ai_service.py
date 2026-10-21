import logging
import requests
from flask import current_app

log = logging.getLogger(__name__)


class AIServiceError(Exception):
    pass


class AIService:
    def generate_reply(self, message: str, history: list = None) -> str:
        history = history or []
        provider = current_app.config.get("AI_PROVIDER", "groq").lower()
        if provider == "openai":
            return self._openai_compatible(
                "https://api.openai.com/v1/chat/completions",
                current_app.config.get("OPENAI_API_KEY", ""),
                "gpt-4o-mini", message, history, "OpenAI",
            )
        if provider == "gemini":
            return self._gemini(message, history)
        return self._openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions",
            current_app.config.get("GROQ_API_KEY", ""),
            current_app.config.get("GROQ_MODEL", "llama-3.1-8b-instant"), message, history, "Groq",
        )

    def _system_prompt(self) -> str:
        return current_app.config.get("BUSINESS_CONTEXT", "Sen yardımcı bir İK asistanısın.")

    def _openai_compatible(self, url, api_key, model, message, history, name):
        if not api_key:
            log.warning("%s API anahtarı yok, demo modu.", name)
            return self._demo()
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": message})
        try:
            r = requests.post(
                url,
                json={"model": model, "messages": messages, "max_tokens": 500, "temperature": 0.7},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=15,
            )
            if r.status_code != 200:
                detail = self._error_detail(r)
                log.error("%s HTTP %s: %s", name, r.status_code, detail)
                raise AIServiceError(f"{name} hatası (HTTP {r.status_code}): {detail}")
            return r.json()["choices"][0]["message"]["content"].strip()
        except AIServiceError:
            raise
        except Exception as e:
            log.error("%s bağlantı hatası: %s", name, e)
            raise AIServiceError(f"{name} servisine bağlanılamadı: {type(e).__name__}")

    def _gemini(self, message, history):
        api_key = current_app.config.get("GEMINI_API_KEY", "")
        if not api_key:
            return self._demo()
        # Gemini rolleri: "user" / "model"
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": message}]})
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                json={
                    "system_instruction": {"parts": [{"text": self._system_prompt()}]},
                    "contents": contents,
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
                },
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            log.error("Gemini hatası: %s", e)
            raise AIServiceError("Gemini servisine ulaşılamadı.")

    @staticmethod
    def _error_detail(r) -> str:
        try:
            return r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            return r.text[:200]

    def _demo(self) -> str:
        return "API anahtarı tanımlı değil, demo moddayım. Lütfen .env dosyanızı kontrol edin."


ai_service = AIService()
