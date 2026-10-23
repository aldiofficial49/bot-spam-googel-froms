import os
from pathlib import Path

from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "sample_form.json"
OUTPUT_DIR = ROOT_DIR / "output"
BROWSERS_DIR = ROOT_DIR / ".browsers"

if BROWSERS_DIR.exists() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)


class AppConfig(BaseModel):
    ollama_url: str = "http://localhost:11434"
    model_name: str = "qwen2.5-coder:1.5b"
    request_timeout: float = Field(default=60.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_iterations: int = Field(default=1000, ge=1, le=100000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    seed: int = 42
    delay: float = Field(default=1.0, ge=0, le=60)
