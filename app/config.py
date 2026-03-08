from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Provider toggles
    transcriber_provider: Literal["mock", "whisper"] = "mock"
    scriptwriter_provider: Literal["mock", "claude"] = "mock"
    voiceover_provider: Literal["mock", "elevenlabs"] = "mock"

    # API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Storage
    data_dir: Path = Path("./data")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"


settings = Settings()
