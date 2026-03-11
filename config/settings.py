from pathlib import Path
from pydantic_settings import BaseSettings

class Settings:
    """Reads from environment. No Pydantic-settings dependency needed."""

    # --- Data ---
    data_dir: Path = Path(os.environ.get("BRIEFMD_DATA_DIR", "data/datasets"))

    # --- LLM API Keys (at least one required) ---
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
    mistral_api_key: str = os.environ.get("MISTRAL_API_KEY", "")
    google_api_key: str = os.environ.get("GOOGLE_API_KEY", "")

    # --- LLM defaults ---
    llm_temperature: float = float(os.environ.get("LLM_TEMPERATURE", "0.1"))
    llm_max_tokens: int = int(os.environ.get("LLM_MAX_TOKENS", "4096"))

    # --- API ---
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8000"))

    # --- Logging ---
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
