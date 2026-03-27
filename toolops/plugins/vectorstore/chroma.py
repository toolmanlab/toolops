"""Chroma vector store plugin — lightweight local-first adapter."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from toolops.plugins.vectorstore.base import VectorStorePlugin

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ChromaPlugin(VectorStorePlugin):
    """Chroma adapter using the official chromadb client.

    Suitable for local development and lightweight deployments.

    Args:
        host:        Chroma server host (used in HTTP mode).
        port:        Chroma server port.
        persist_dir: Local persistence directory (used in embedded mode).
        use_http:    If True, connect to a remote Chroma HTTP server.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        persist_dir: str = "./.chroma",
        *,
        use_http: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.persist_dir = persist_dir
        self.use_http = use_http
        self._client: Any = None

    # ── Lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to (or initialize) Chroma."""
        try:
            import chromadb

            if self.use_http:
                self._client = chromadb.HttpClient(host=self.host, port=self.port)
            else:
                self._client = chromadb.PersistentClient(path=self.persist_dir)
            logger.info("ChromaPlugin connected (http=%s)", self.use_http)
            return True
        except ImportError:
            logger.error("chromadb not installed. Run: pip install toolops[chroma]")
            return False
        except Exception as exc:
            logger.error("ChromaPlugin connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Release Chroma client resources."""
        self._client = None

    # ── Collection management ─────────────────────────────────

    def create_collection(self, name: str, dim: int) -> bool:
        """Create or retrieve a Chroma collection.

        Chroma infers dimensionality from the first inserted vector,
        so ``dim`` is stored in collection metadata for documentation only.
        """
        try:
            self._client.get_or_create_collection(
                name=name,
                metadata={"dim": dim, "hnsw:space": "cosine"},
            )
            logger.debug("Collection '%s' ready (dim=%d)", name, dim)
            return True
        except Exception as exc:
            logger.error("create_collection failed: %s", exc)
            return False

    def delete_collection(self, name: str) -> bool:
        """Delete a Chroma collection."""
        try:
            self._client.delete_collection(name)
            return True
        except Exception as exc:
            logger.error("delete_collection '%s' failed: %s", name, exc)
            return False

    def list_collections(self) -> list[str]:
        """Return names of all Chroma collections."""
        try:
            return [c.name for c in self._client.list_collections()]
        except Exception as exc:
            logger.error("list_collections failed: %s", exc)
            return []

    # ── Data operations ───────────────────────────────────────

    def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, object]],
    ) -> list[str]:
        """Insert vectors into a Chroma collection."""
        try:
            col = self._client.get_collection(collection)
            ids = [str(uuid.uuid4()) for _ in vectors]
            col.add(embeddings=vectors, metadatas=metadata, ids=ids)
            return ids
        except Exception as exc:
            logger.error("insert failed: %s", exc)
            return []

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, object]]:
        """Query nearest neighbours from a Chroma collection."""
        try:
            col = self._client.get_collection(collection)
            results = col.query(query_embeddings=[query_vector], n_results=top_k)
            output: list[dict[str, object]] = []
            for idx, doc_id in enumerate(results["ids"][0]):
                output.append(
                    {
                        "id": doc_id,
                        "score": results["distances"][0][idx],
                        "metadata": results["metadatas"][0][idx],
                    }
                )
            return output
        except Exception as exc:
            logger.error("search failed: %s", exc)
            return []

    def delete(self, collection: str, ids: list[str]) -> bool:
        """Delete vectors by ID from a Chroma collection."""
        try:
            col = self._client.get_collection(collection)
            col.delete(ids=ids)
            return True
        except Exception as exc:
            logger.error("delete failed: %s", exc)
            return False
