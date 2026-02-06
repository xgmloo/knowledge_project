from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    pdf_dir: Path = Path("data/pdfs")
    output_dir: Path = Path("data/outputs")
    images_dir: Path = Path("data/outputs/images")
    chunks_file: Path = Path("data/outputs/chunks.jsonl")
    extraction_file: Path = Path("data/outputs/extractions.jsonl")

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11500")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3-vl:30b")

    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password123")


def ensure_dirs(settings: Settings) -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
