"""Runtime configuration for the local-first API.

Implements docs/08_SYSTEM_ARCHITECTURE.md and docs/26_CONFIGURATION.md:
provider calls and data paths are explicit configuration, never hidden defaults.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "DuckDocs API"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_origin: str = "http://localhost:3000"
    data_root: Path = Path("data")
    max_file_size: int = 50 * 1024 * 1024
    local_model: str = "gemma3:1b"
    chat_model: str = "gemma3:1b"
    embed_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    top_k: int = 12
    min_similarity: float = 0.35
    relevance_high_threshold: float = 0.75
    relevance_medium_threshold: float = 0.5
    db_url: str | None = None
    chroma_url: str | None = None
    api_token: str | None = None
    summarize_with_model: bool = True
    ocr_engine: str = "auto"
    ocr_languages: str = "eng"
    ocr_model_dir: str | None = None
    ocr_batch_size: int = 8
    ocr_dpi: int = 300
    ocr_min_chars_per_page: int = 40
    chunk_max_words: int = 180
    chunk_overlap_words: int = 30
    max_chunks_per_document: int = 4000

    @classmethod
    def from_env(cls) -> "Settings":
        data_root = Path(os.getenv("DUCKDOCS_DATA_ROOT", "data"))
        db_url = os.getenv("DUCKDOCS_DB_URL") or None
        chroma_url = os.getenv("DUCKDOCS_CHROMA_URL") or os.getenv("CHROMA_URL") or None
        return cls(
            host=os.getenv("DUCKDOCS_API_HOST", "0.0.0.0"),
            port=int(os.getenv("DUCKDOCS_API_PORT", "8000")),
            frontend_origin=os.getenv("DUCKDOCS_FRONTEND_ORIGIN", "http://localhost:3000"),
            data_root=data_root,
            max_file_size=int(os.getenv("DUCKDOCS_MAX_FILE_SIZE", str(50 * 1024 * 1024))),
            local_model=os.getenv("DUCKDOCS_LOCAL_MODEL", "gemma3:1b"),
            chat_model=os.getenv("DUCKDOCS_CHAT_MODEL", os.getenv("DUCKDOCS_LOCAL_MODEL", "gemma3:1b")),
            embed_model=os.getenv("DUCKDOCS_EMBED_MODEL", "nomic-embed-text"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
            top_k=int(os.getenv("DUCKDOCS_TOP_K", "12")),
            min_similarity=float(os.getenv("DUCKDOCS_MIN_SIMILARITY", "0.35")),
            relevance_high_threshold=float(os.getenv("DUCKDOCS_RELEVANCE_HIGH_THRESHOLD", "0.75")),
            relevance_medium_threshold=float(os.getenv("DUCKDOCS_RELEVANCE_MEDIUM_THRESHOLD", "0.5")),
            db_url=db_url,
            chroma_url=chroma_url,
            api_token=os.getenv("DUCKDOCS_API_TOKEN") or None,
            summarize_with_model=os.getenv("DUCKDOCS_SUMMARIZE_WITH_MODEL", "1") not in {"0", "false", "False"},
            ocr_engine=os.getenv("DUCKDOCS_OCR_ENGINE", "auto"),
            ocr_languages=os.getenv("DUCKDOCS_OCR_LANGUAGES", "eng"),
            ocr_model_dir=os.getenv("DUCKDOCS_OCR_MODEL_DIR") or None,
            ocr_batch_size=int(os.getenv("DUCKDOCS_OCR_BATCH_SIZE", "8")),
            ocr_dpi=int(os.getenv("DUCKDOCS_OCR_DPI", "300")),
            ocr_min_chars_per_page=int(os.getenv("DUCKDOCS_OCR_MIN_CHARS_PER_PAGE", "40")),
            chunk_max_words=int(os.getenv("DUCKDOCS_CHUNK_MAX_WORDS", "180")),
            chunk_overlap_words=int(os.getenv("DUCKDOCS_CHUNK_OVERLAP_WORDS", "30")),
            max_chunks_per_document=int(os.getenv("DUCKDOCS_MAX_CHUNKS_PER_DOCUMENT", "4000")),
        )


settings = Settings.from_env()
