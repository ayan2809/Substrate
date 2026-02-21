"""Substrate Memory — Phase 2: SQLite (chronological) + ChromaDB (semantic recall)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb


# ── Storage root ──────────────────────────────────────────────────────
SUBSTRATE_DIR = Path.home() / ".substrate"
SQLITE_PATH = SUBSTRATE_DIR / "substrate.db"
CHROMA_PATH = SUBSTRATE_DIR / "chroma_db"


class SubstrateMemory:
    """Manages dual persistent memory: SQLite for session state, ChromaDB for semantic recall."""

    def __init__(self) -> None:
        """Initialise both storage backends and generate a fresh session UUID."""
        SUBSTRATE_DIR.mkdir(parents=True, exist_ok=True)

        self.session_uuid = uuid.uuid4().hex

        # — SQLite (chronological) —
        self._conn = sqlite3.connect(str(SQLITE_PATH))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT    NOT NULL,
                timestamp    TEXT    NOT NULL,
                role         TEXT    NOT NULL,
                content      TEXT    NOT NULL
            )
            """
        )
        self._conn.commit()

        # — ChromaDB (semantic) —
        self._chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self._collection = self._chroma.get_or_create_collection(
            name="substrate_insights",
        )

    # ── Write (Dual) ──────────────────────────────────────────────────

    def save(self, user_input: str, model_response: str) -> None:
        """
        Dual-write an interaction pair.

        1. Two rows into SQLite (user + model), tagged with session_uuid.
        2. One combined document into ChromaDB for semantic retrieval.
        """
        now = datetime.now(timezone.utc).isoformat()
        interaction_id = uuid.uuid4().hex

        # SQLite — two rows
        self._conn.executemany(
            "INSERT INTO sessions (session_uuid, timestamp, role, content) VALUES (?, ?, ?, ?)",
            [
                (self.session_uuid, now, "user", user_input),
                (self.session_uuid, now, "model", model_response),
            ],
        )
        self._conn.commit()

        # ChromaDB — one combined document
        combined = f"User: {user_input}\nSubstrate: {model_response}"
        self._collection.upsert(
            ids=[interaction_id],
            documents=[combined],
            metadatas=[{"session_uuid": self.session_uuid, "timestamp": now}],
        )

    # ── Read: Chronological (current session) ─────────────────────────

    def get_recent(self, n: int = 10) -> list[dict]:
        """
        Return the last `n` messages for the current session in chronological order.

        Returns:
            List of dicts with keys: role, content.
        """
        rows = self._conn.execute(
            """
            SELECT role, content FROM sessions
            WHERE session_uuid = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.session_uuid, n),
        ).fetchall()

        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── Read: Semantic (cross-session) ────────────────────────────────

    def get_similar(self, query: str, n: int = 2) -> list[str]:
        """
        Return the top `n` semantically similar past interactions across all sessions.

        Cold-start safe: returns an empty list if the collection is empty.

        Args:
            query: The text to match against.
            n: Number of results to return.

        Returns:
            List of combined interaction strings.
        """
        total = self._collection.count()
        if total == 0:
            return []

        actual_n = min(n, total)
        results = self._collection.query(
            query_texts=[query],
            n_results=actual_n,
        )

        docs = results.get("documents")
        if docs and docs[0]:
            return docs[0]
        return []

    def total_insights(self) -> int:
        """Return the total number of interactions stored in ChromaDB."""
        return self._collection.count()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()
