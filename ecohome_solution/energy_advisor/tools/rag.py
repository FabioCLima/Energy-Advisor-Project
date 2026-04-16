from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..schemas import RagSearchResult
from ..services.retrieval import ensure_vectorstore, list_document_paths


@tool
def search_energy_tips(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the energy-saving knowledge base using semantic similarity (RAG).

    Returns ranked tips from curated energy-efficiency documents.

    Args:
        query: Natural-language search query.
        max_results: Maximum number of results to return (default 5).
    """
    if not query or not query.strip():
        return {"error": "query must be a non-empty string."}
    if not (1 <= max_results <= 20):
        return {"error": "max_results must be between 1 and 20."}

    try:
        settings = Settings()
        doc_paths = list_document_paths(settings.documents_dir)
        logger.debug(
            "search_energy_tips | query='{}' docs={} store={}",
            query, len(doc_paths), settings.vectorstore_dir,
        )

        vectorstore = ensure_vectorstore(
            persist_directory=settings.vectorstore_dir,
            document_paths=doc_paths,
            api_key=settings.selected_api_key(),
            base_url=settings.base_url,
        )
        docs = vectorstore.similarity_search(query, k=max_results)

        payload = {
            "query": query,
            "total_results": len(docs),
            "tips": [
                {
                    "rank": i + 1,
                    "content": doc.page_content,
                    "source": (doc.metadata or {}).get("source", "unknown"),
                    "relevance_score": "high" if i < 2 else "medium" if i < 4 else "low",
                }
                for i, doc in enumerate(docs)
            ],
        }
        validated = RagSearchResult.model_validate(payload)
        return validated.model_dump()
    except Exception as exc:
        logger.exception("search_energy_tips failed")
        return {"error": f"Failed to search energy tips: {exc}"}
