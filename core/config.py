from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str
    llm_model: str
    data_dir: Path
    timezone: str


settings = Settings()