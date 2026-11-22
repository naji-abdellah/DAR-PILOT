"""RAG pipeline for DarPilot listings.

Chunks listing text, embeds chunks with fastembed (CPU, ONNX), stores
embeddings in SQLite, and returns the top-k most similar chunks for a query
using cosine similarity.

Design notes (owner is learning):
- Vectors live in the same SQLite DB as the rest of the app (one table,
  ``rag_chunks``). No separate vector server, which keeps memory use low on
  an 8 GB RAM / no-GPU machine.
- Embeddings are stored as raw float32 bytes (BLOB) for compactness.
- Cosine similarity is computed in Python over all stored chunks. With ~100
  listings this is fast enough; for larger corpora a real vector index would
  be needed.
- The fastembed model (bge-small-en-v1.5, 384 dims) is downloaded once into a
  cache dir and reused.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import numpy as np
from fastembed import TextEmbedding

from backend.database import get_connection

# ── Model ──────────────────────────────────────────────────────────────────
# Loaded once and reused across calls so we don't re-download/re-initialize.
_model: Optional[TextEmbedding] = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding()  # downloads default model on first use
    return _model


# ── Connection helper ──────────────────────────────────────────────────────

@contextmanager
def _conn_context(conn: Optional[sqlite3.Connection]):
    """Yield ``conn`` if given, otherwise open a fresh one from get_connection."""
    if conn is not None:
        yield conn
    else:
        with get_connection() as c:
            yield c


# ── Schema ─────────────────────────────────────────────────────────────────

RAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id   INTEGER    NOT NULL,
    chunk_index  INTEGER    NOT NULL,
    chunk_text   TEXT       NOT NULL,
    embedding    BLOB       NOT NULL,   -- float32 raw bytes
    created_at   TEXT       NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_listing_id ON rag_chunks(listing_id);
"""


def _init_rag_table(conn: sqlite3.Connection) -> None:
    conn.executescript(RAG_SCHEMA)
    conn.commit()


def init_rag_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the ``rag_chunks`` table if it does not exist."""
    with _conn_context(conn) as c:
        _init_rag_table(c)


def _clear_rag_chunks(conn: sqlite3.Connection) -> None:
    """Remove all existing chunks (called before rebuilding the index)."""
    conn.execute("DELETE FROM rag_chunks")
    conn.commit()


# ── Chunking ───────────────────────────────────────────────────────────────

def chunk_text(text: str, max_words: int = 60) -> List[str]:
    """Split ``text`` into chunks of at most ``max_words`` words.

    Simple whitespace-based chunking so the code stays easy to explain.
    """
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i : i + max_words]))
    return chunks


def _embedding_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _embedding_from_blob(buf: bytes) -> np.ndarray:
    return np.frombuffer(buf, dtype=np.float32)


# ── Build / rebuild index ──────────────────────────────────────────────────

def _build_index(
    listings: List[Dict[str, Any]], chunk_size: int, conn: sqlite3.Connection
) -> int:
    _init_rag_table(conn)
    _clear_rag_chunks(conn)
    model = _get_model()

    entries: List[tuple] = []  # (listing_id, chunk_index, chunk_text)
    for listing in listings:
        listing_id = listing["id"]
        text = f"{listing.get('title', '')}. {listing.get('description', '')}".strip()
        chunks = chunk_text(text, max_words=chunk_size)
        for idx, chunk in enumerate(chunks):
            entries.append((listing_id, idx, chunk))

    texts = [e[2] for e in entries]
    vectors = list(model.embed(texts)) if texts else []

    rows = []
    for (listing_id, chunk_index, chunk_txt), vector in zip(entries, vectors):
        rows.append(
            (listing_id, chunk_index, chunk_txt, _embedding_blob(vector))
        )

    if rows:
        conn.executemany(
            """INSERT INTO rag_chunks
               (listing_id, chunk_index, chunk_text, embedding)
               VALUES (?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(rows)


def build_index(
    listings: List[Dict[str, Any]], chunk_size: int = 60,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """Chunk, embed, and store all listings. Returns number of chunks stored.

    Rebuilds the index from scratch (clears existing chunks first).
    """
    with _conn_context(conn) as c:
        return _build_index(listings, chunk_size, c)


# ── Search ─────────────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (0..1, higher = more similar)."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def search(
    query: str, top_k: int = 5, chunk_size: int = 60,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """Return the top-k chunks most similar to ``query``.

    Each result dict includes the listing metadata (for citation) plus the
    matched chunk text and its cosine-similarity score.

    Auto-builds the index when empty so search works against the listings
    currently in the database (useful after a fresh DB / test reset).
    """
    with _conn_context(conn) as c:
        _init_rag_table(c)
        count = c.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
        if count == 0:
            from backend import repositories

            listings = repositories.get_all_listings()
            _build_index(listings, chunk_size, c)

        model = _get_model()
        query_vector = np.asarray(next(model.embed([query])), dtype=np.float32)

        rows = c.execute(
            """SELECT rc.listing_id, rc.chunk_index, rc.chunk_text, rc.embedding,
                      l.title, l.city, l.neighborhood, l.price_mad,
                      l.property_type, l.status
               FROM rag_chunks rc
               JOIN listings l ON l.id = rc.listing_id"""
        ).fetchall()

        scored: List[Dict[str, Any]] = []
        for (listing_id, chunk_index, chunk_text, emb_buf,
             title, city, neighborhood, price_mad,
             property_type, status) in rows:
            vec = _embedding_from_blob(emb_buf)
            score = _cosine_similarity(query_vector, vec)
            scored.append({
                "listing_id": listing_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "score": score,
                "title": title,
                "city": city,
                "neighborhood": neighborhood,
                "price_mad": price_mad,
                "property_type": property_type,
                "status": status,
            })

        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]
