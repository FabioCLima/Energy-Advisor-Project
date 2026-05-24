"""Tests for energy_advisor.services.retrieval — hybrid BM25 + semantic retriever."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.embeddings.fake import FakeEmbeddings

from energy_advisor.services.retrieval import (
    _load_splits,
    build_hybrid_retriever,
    list_document_paths,
)

# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def docs_dir(tmp_path):
    """Two .txt knowledge base documents in a temp directory."""
    (tmp_path / "ev_tips.txt").write_text(
        "Tesla Model 3 charges best during off-peak hours between midnight and 5 AM. "
        "Use the built-in scheduling function to set a departure time."
    )
    (tmp_path / "solar_tips.txt").write_text(
        "Solar panels generate most energy between 10 AM and 2 PM. "
        "Align heavy consumption with solar peak to maximise self-sufficiency."
    )
    return tmp_path


@pytest.fixture()
def doc_paths(docs_dir):
    return list_document_paths(str(docs_dir))


# ── list_document_paths ───────────────────────────────────────────────


def test_list_document_paths_returns_txt_files(docs_dir, doc_paths):
    assert len(doc_paths) == 2
    assert all(p.endswith(".txt") for p in doc_paths)


def test_list_document_paths_empty_dir(tmp_path):
    assert list_document_paths(str(tmp_path)) == []


def test_list_document_paths_nonexistent_dir():
    assert list_document_paths("/nonexistent/path") == []


def test_list_document_paths_sorted(doc_paths):
    assert doc_paths == sorted(doc_paths)


# ── _load_splits ──────────────────────────────────────────────────────


def test_load_splits_returns_documents(doc_paths):
    splits = _load_splits(doc_paths)
    assert len(splits) >= 2  # at least one chunk per file


def test_load_splits_ignores_missing_files(doc_paths):
    paths_with_missing = doc_paths + ["/nonexistent/file.txt"]
    splits = _load_splits(paths_with_missing)
    assert len(splits) >= 2  # missing file skipped gracefully


def test_load_splits_empty_list():
    assert _load_splits([]) == []


# ── build_hybrid_retriever ────────────────────────────────────────────
# Patch OpenAIEmbeddings to avoid real API calls.
# FakeEmbeddings produces random-but-valid vectors — enough to build a Chroma index.


@pytest.fixture()
def fake_embeddings():
    return FakeEmbeddings(size=768)


def test_hybrid_retriever_returns_documents(docs_dir, doc_paths, fake_embeddings, tmp_path):
    """Hybrid retriever must return Document objects for any query."""
    with patch("energy_advisor.services.retrieval.OpenAIEmbeddings", return_value=fake_embeddings):
        retriever = build_hybrid_retriever(
            persist_directory=str(tmp_path / "vs"),
            document_paths=doc_paths,
            k=2,
        )
        results = retriever.invoke("Tesla off-peak charging")

    assert len(results) >= 1
    assert all(hasattr(d, "page_content") for d in results)


def test_hybrid_retriever_bm25_surfaces_keyword_match(docs_dir, doc_paths, fake_embeddings, tmp_path):
    """BM25 component must surface the Tesla doc for a Tesla-specific query."""
    with patch("energy_advisor.services.retrieval.OpenAIEmbeddings", return_value=fake_embeddings):
        retriever = build_hybrid_retriever(
            persist_directory=str(tmp_path / "vs"),
            document_paths=doc_paths,
            k=2,
        )
        results = retriever.invoke("Tesla Model 3")

    contents = " ".join(d.page_content for d in results)
    assert "Tesla" in contents


def test_hybrid_retriever_no_duplicate_documents(docs_dir, doc_paths, fake_embeddings, tmp_path):
    """RRF fusion must not return the same chunk twice."""
    with patch("energy_advisor.services.retrieval.OpenAIEmbeddings", return_value=fake_embeddings):
        retriever = build_hybrid_retriever(
            persist_directory=str(tmp_path / "vs"),
            document_paths=doc_paths,
            k=3,
        )
        results = retriever.invoke("energy savings")

    contents = [d.page_content for d in results]
    assert len(contents) == len(set(contents)), "Duplicate documents returned"


def test_hybrid_retriever_solar_query(docs_dir, doc_paths, fake_embeddings, tmp_path):
    """Retriever must surface the solar doc for a solar-specific query."""
    with patch("energy_advisor.services.retrieval.OpenAIEmbeddings", return_value=fake_embeddings):
        retriever = build_hybrid_retriever(
            persist_directory=str(tmp_path / "vs"),
            document_paths=doc_paths,
            k=2,
        )
        results = retriever.invoke("solar panels peak hours")

    contents = " ".join(d.page_content for d in results)
    assert "solar" in contents.lower() or "Solar" in contents
