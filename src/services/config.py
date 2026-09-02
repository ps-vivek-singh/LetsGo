import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)


class Config:
    @classmethod
    def reload(cls) -> None:
        """Reload .env file to pick up newly added API keys."""
        load_dotenv(dotenv_path=_ENV_PATH, override=True)

    @classmethod
    def get_llm_key(cls) -> str:
        cls.reload()
        raw_key = (
            os.getenv("NVIDIA_API_KEY", "").strip()
            or os.getenv("LLM_API_KEY", "").strip()
            or os.getenv("GROQ_API_KEY", "").strip()
            or os.getenv("GEMINI_API_KEY", "").strip()
            or os.getenv("OPENROUTER_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
            or os.getenv("XAI_API_KEY", "").strip()
        )
        return raw_key.strip('"\'')

    @classmethod
    def get_llm_model(cls) -> str:
        cls.reload()
        model = (
            os.getenv("NVIDIA_MODEL", "").strip()
            or os.getenv("LLM_MODEL", "").strip()
            or os.getenv("XAI_MODEL", "").strip()
        )
        model = model.strip('"\'')
        if model.startswith('g"') or model.startswith("g'"):
            model = model[2:-1]
        return model

    @classmethod
    def get_gmail_user(cls) -> str:
        cls.reload()
        return (os.getenv("GMAIL_USER") or os.getenv("SMTP_USER", "")).strip().strip('"\'')

    @classmethod
    def get_gmail_password(cls) -> str:
        cls.reload()
        pwd = (os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD", "")).strip().strip('"\'')
        return pwd.replace(" ", "")

    @classmethod
    def get_recipient_email(cls) -> str:
        cls.reload()
        return (os.getenv("RECIPIENT_EMAIL") or os.getenv("DEFAULT_RECIPIENT_EMAIL", "")).strip().strip('"\'')

    @classmethod
    def get_smtp_host(cls) -> str:
        cls.reload()
        return (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip().strip('"\'')

    @classmethod
    def get_smtp_port(cls) -> int:
        cls.reload()
        val = os.getenv("SMTP_PORT", "465").strip().strip('"\'')
        try:
            return int(val)
        except ValueError:
            return 465

    @classmethod
    def get_mcp_mode(cls) -> str:
        cls.reload()
        return (os.getenv("MCP_MODE") or "in_process").strip().lower()

    # Backwards compatibility helpers
    get_xai_key = get_llm_key
    get_xai_model = get_llm_model

    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY", "")
    TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
    OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")

    # LLM Engines (NVIDIA NIM / Groq / OpenRouter / OpenAI)
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "")

    # Gmail / Email MCP Tool
    GMAIL_USER = os.getenv("GMAIL_USER", os.getenv("SMTP_USER", ""))
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


