from __future__ import annotations

import os
from typing import Any

from langchain_chroma import Chroma
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from rank_bm25 import BM25Okapi

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200


class _BM25Retriever(BaseRetriever):
    """Thin BM25Okapi wrapper — replaces langchain_community.BM25Retriever."""

    docs: list[Document]
    k: int = 5
    _bm25: Any = None

    def model_post_init(self, __context: Any) -> None:
        tokenized = [doc.page_content.lower().split() for doc in self.docs]
        self._bm25 = BM25Okapi(tokenized)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        scores = self._bm25.get_scores(query.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: self.k]
        return [self.docs[i] for i in top_indices]

    @classmethod
    def from_documents(cls, documents: list[Document], k: int = 5) -> "_BM25Retriever":
        return cls(docs=documents, k=k)


def _load_splits(document_paths: list[str]) -> list[Document]:
    """Load .txt documents and split into chunks for indexing."""
    documents: list[Document] = []
    for path in document_paths:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            documents.append(Document(page_content=text, metadata={"source": path}))
            logger.debug("Loaded document: {}", path)
        else:
            logger.warning("Document not found, skipping: {}", path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP
    )
    return splitter.split_documents(documents)


def ensure_vectorstore(
    persist_directory: str,
    document_paths: list[str],
    api_key: str | None = None,
    base_url: str | None = None,
) -> Chroma:
    """
    Return a Chroma vectorstore, building it from documents if it does not exist yet.

    Idempotent: if the store already has a chroma.sqlite3 file, it is opened
    as-is without re-ingesting documents.

    Args:
        persist_directory: Path to the ChromaDB directory.
        document_paths: List of .txt document paths to index.
        api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
        base_url: Optional custom OpenAI-compatible endpoint.
    """
    os.makedirs(persist_directory, exist_ok=True)
    chroma_db_file = os.path.join(persist_directory, "chroma.sqlite3")
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("VOCAREUM_API_KEY")
    resolved_url = base_url or os.environ.get("ENERGY_ADVISOR_BASE_URL")
    embeddings = OpenAIEmbeddings(
        **({"openai_api_key": resolved_key} if resolved_key else {}),
        **({"base_url": resolved_url} if resolved_url else {}),
    )

    if not os.path.exists(chroma_db_file):
        logger.info("Vectorstore not found — building from {} document(s)", len(document_paths))
        splits = _load_splits(document_paths)
        logger.info("Indexed {} chunks into vectorstore at {}", len(splits), persist_directory)
        return Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=persist_directory,
        )

    logger.debug("Vectorstore found at {} — reusing existing index", persist_directory)
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)


def build_hybrid_retriever(
    persist_directory: str,
    document_paths: list[str],
    k: int = 5,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EnsembleRetriever:
    """Build a hybrid BM25 + semantic retriever with Reciprocal Rank Fusion (RRF).

    BM25 handles exact keyword queries (e.g. "Tesla", "ANEEL", "bandeira vermelha").
    Semantic search handles conceptual queries (e.g. "como economizar energia?").
    RRF fuses both ranked lists: score = sum(1 / (k + rank_i)) — no re-ranking model needed.

    Args:
        persist_directory: ChromaDB persist directory.
        document_paths: Paths to .txt knowledge base documents.
        k: Number of candidates per retriever before fusion.
        api_key: OpenAI API key for embeddings.
        base_url: Optional custom OpenAI-compatible endpoint.

    Returns:
        EnsembleRetriever with equal weights [0.5 BM25, 0.5 semantic].
    """
    splits = _load_splits(document_paths)

    bm25 = _BM25Retriever.from_documents(splits, k=k)

    vectorstore = ensure_vectorstore(persist_directory, document_paths, api_key, base_url)
    semantic = vectorstore.as_retriever(search_kwargs={"k": k})

    return EnsembleRetriever(retrievers=[bm25, semantic], weights=[0.5, 0.5])


def list_document_paths(documents_dir: str) -> list[str]:
    """Return sorted list of all .txt files found in documents_dir."""
    if not os.path.isdir(documents_dir):
        return []
    return sorted(
        os.path.join(documents_dir, f)
        for f in os.listdir(documents_dir)
        if f.endswith(".txt")
    )
