from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..schemas import RagSearchResult
from ..services.retrieval import build_hybrid_retriever, list_document_paths


@tool
def search_energy_tips(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the energy-saving knowledge base using hybrid RAG (BM25 + semantic search).

    Combines keyword matching (BM25) and semantic similarity via Reciprocal Rank Fusion.
    BM25 excels at exact terms like "Tesla", "ANEEL", "bandeira vermelha".
    Semantic search handles conceptual queries like "como economizar energia no inverno?".

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
            "search_energy_tips | query='{}' docs={} store={} retriever=hybrid_bm25_semantic",
            query, len(doc_paths), settings.vectorstore_dir,
        )

        retriever = build_hybrid_retriever(
            persist_directory=settings.vectorstore_dir,
            document_paths=doc_paths,
            k=max_results,
            api_key=settings.selected_api_key(),
            base_url=settings.base_url,
        )
        docs = retriever.invoke(query)

        payload = {
            "query": query,
            "retrieval_method": "hybrid_bm25_semantic",
            "total_results": len(docs),
            "tips": [
                {
                    "rank": i + 1,
                    "content": doc.page_content,
                    # Basename only: this is the exact token the model must cite
                    # as `(source: <filename>)` — handing it a full path invites
                    # citations that don't match the knowledge base contract.
                    "source": os.path.basename((doc.metadata or {}).get("source", "unknown")),
                }
                for i, doc in enumerate(docs)
            ],
        }
        validated = RagSearchResult.model_validate(payload)
        return validated.model_dump()
    except Exception as exc:
        logger.exception("search_energy_tips failed")
        return {"error": f"Failed to search energy tips: {exc}"}
