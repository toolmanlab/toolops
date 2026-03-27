"""Qdrant vector store plugin — cloud-native adapter."""

from __future__ import annotations

import logging
import uuid

from toolops.plugins.vectorstore.base import VectorStorePlugin

logger = logging.getLogger(__name__)


class QdrantPlugin(VectorStorePlugin):
    """Qdrant adapter using the official qdrant-client SDK.

    Supports both self-hosted and Qdrant Cloud deployments.

    Args:
        host:    Qdrant server host.
        port:    Qdrant REST/gRPC port (default 6333).
        api_key: Qdrant Cloud API key (optional for self-hosted).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self._client: object | None = None

    # ── Lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to the Qdrant server."""
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-untyped]

            kwargs: dict[str, object] = {"host": self.host, "port": self.port, "prefer_grpc": True}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = QdrantClient(**kwargs)  # type: ignore[arg-type]
            logger.info("QdrantPlugin connected to %s:%d", self.host, self.port)
            return True
        except ImportError:
            logger.error("qdrant-client not installed. Run: pip install toolops[qdrant]")
            return False
        except Exception as exc:
            logger.error("QdrantPlugin connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Close the Qdrant client."""
        self._client = None

    # ── Collection management ─────────────────────────────────

    def create_collection(self, name: str, dim: int) -> bool:
        """Create a Qdrant collection with cosine distance."""
        try:
            from qdrant_client.models import Distance, VectorParams  # type: ignore[import-untyped]

            assert self._client is not None
            existing = [c.name for c in self._client.get_collections().collections]  # type: ignore[union-attr]
            if name in existing:
                return True
            self._client.create_collection(  # type: ignore[union-attr]
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection '%s' created (dim=%d)", name, dim)
            return True
        except Exception as exc:
            logger.error("create_collection failed: %s", exc)
            return False

    def delete_collection(self, name: str) -> bool:
        """Delete a Qdrant collection."""
        try:
            assert self._client is not None
            self._client.delete_collection(collection_name=name)  # type: ignore[union-attr]
            return True
        except Exception as exc:
            logger.error("delete_collection failed: %s", exc)
            return False

    def list_collections(self) -> list[str]:
        """Return all Qdrant collection names."""
        try:
            assert self._client is not None
            return [c.name for c in self._client.get_collections().collections]  # type: ignore[union-attr]
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
        """Upsert vectors with payload into a Qdrant collection."""
        try:
            from qdrant_client.models import PointStruct  # type: ignore[import-untyped]

            assert self._client is not None
            ids = [str(uuid.uuid4()) for _ in vectors]
            points = [
                PointStruct(id=uid, vector=vec, payload=meta)
                for uid, vec, meta in zip(ids, vectors, metadata)
            ]
            self._client.upsert(collection_name=collection, points=points)  # type: ignore[union-attr]
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
        """Cosine nearest-neighbour search in a Qdrant collection."""
        try:
            assert self._client is not None
            results = self._client.search(  # type: ignore[union-attr]
                collection_name=collection,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )
            return [
                {"id": str(r.id), "score": r.score, "metadata": r.payload or {}}
                for r in results
            ]
        except Exception as exc:
            logger.error("search failed: %s", exc)
            return []

    def delete(self, collection: str, ids: list[str]) -> bool:
        """Delete vectors by ID from a Qdrant collection."""
        try:
            from qdrant_client.models import PointIdsList  # type: ignore[import-untyped]

            assert self._client is not None
            self._client.delete(  # type: ignore[union-attr]
                collection_name=collection,
                points_selector=PointIdsList(points=ids),  # type: ignore[arg-type]
            )
            return True
        except Exception as exc:
            logger.error("delete failed: %s", exc)
            return False
