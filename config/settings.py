from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # LLM — Mistral via Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # Data
    data_dir: Path = Path("./data/datasets")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Features
    demo_mode: bool = False


settings = Settings()
