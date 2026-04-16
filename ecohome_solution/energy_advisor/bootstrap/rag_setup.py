"""
Bootstrap step 3: RAG vectorstore initialisation.

Reads all .txt documents from the configured documents directory, splits them
into chunks, and indexes them into a ChromaDB vector store.

Usage:
    python -m energy_advisor.bootstrap.rag_setup
"""
from __future__ import annotations

import os

from loguru import logger

from ..config import Settings
from ..services.retrieval import ensure_vectorstore, list_document_paths


def _load_env() -> None:
    """Load .env file so OPENAI_API_KEY is available for embeddings."""
    try:
        from dotenv import load_dotenv  # type: ignore

        for candidate in (".env", os.path.join("..", ".env")):
            if os.path.exists(candidate):
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass


def setup_vectorstore(settings: Settings | None = None) -> None:
    """Build the ChromaDB vectorstore from all documents in documents_dir.

    Idempotent — skips re-indexing if the store already exists.

    Args:
        settings: Optional Settings instance.
    """
    settings = settings or Settings()
    doc_paths = list_document_paths(settings.documents_dir)

    if not doc_paths:
        logger.warning(
            "No .txt documents found in '{}'. "
            "Add documents before running rag_setup.",
            settings.documents_dir,
        )
        return

    logger.info(
        "Indexing {} document(s) into vectorstore at '{}'",
        len(doc_paths),
        settings.vectorstore_dir,
    )
    for p in doc_paths:
        logger.debug("  - {}", os.path.basename(p))

    ensure_vectorstore(
        persist_directory=settings.vectorstore_dir,
        document_paths=doc_paths,
        api_key=settings.selected_api_key(),
        base_url=settings.base_url,
    )
    logger.info("Vectorstore ready.")


if __name__ == "__main__":
    _load_env()
    setup_vectorstore()
