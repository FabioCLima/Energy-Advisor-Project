from __future__ import annotations

import os

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger


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
    # Resolve key: explicit arg → env var (set by load_dotenv or shell)
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("VOCAREUM_API_KEY")
    resolved_url = base_url or os.environ.get("ENERGY_ADVISOR_BASE_URL")
    embeddings = OpenAIEmbeddings(
        **({"openai_api_key": resolved_key} if resolved_key else {}),
        **({"base_url": resolved_url} if resolved_url else {}),
    )

    if not os.path.exists(chroma_db_file):
        logger.info("Vectorstore not found — building from {} document(s)", len(document_paths))
        documents = []
        for path in document_paths:
            if os.path.exists(path):
                loader = TextLoader(path)
                documents.extend(loader.load())
                logger.debug("Loaded document: {}", path)
            else:
                logger.warning("Document not found, skipping: {}", path)

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(documents)
        logger.info("Indexed {} chunks into vectorstore at {}", len(splits), persist_directory)

        return Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=persist_directory,
        )

    logger.debug("Vectorstore found at {} — reusing existing index", persist_directory)
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)


def list_document_paths(documents_dir: str) -> list[str]:
    """Return sorted list of all .txt files found in documents_dir."""
    if not os.path.isdir(documents_dir):
        return []
    return sorted(
        os.path.join(documents_dir, f)
        for f in os.listdir(documents_dir)
        if f.endswith(".txt")
    )
