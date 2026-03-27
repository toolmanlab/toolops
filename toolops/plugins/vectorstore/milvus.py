"""Milvus vector store plugin — production-scale adapter."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from toolops.plugins.vectorstore.base import VectorStorePlugin

logger = logging.getLogger(__name__)


class MilvusPlugin(VectorStorePlugin):
    """Milvus adapter using the official pymilvus SDK.

    Designed for high-throughput, distributed deployments.

    Args:
        host:  Milvus server host.
        port:  Milvus gRPC port (default 19530).
        token: Authentication token (leave empty for no-auth setups).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        token: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self._connected: bool = False
        self._collections: dict[str, Any] = {}

    # ── Lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to Milvus via gRPC."""
        try:
            from pymilvus import connections  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {"host": self.host, "port": self.port}
            if self.token:
                kwargs["token"] = self.token
            connections.connect(alias="default", **kwargs)
            self._connected = True
            logger.info("MilvusPlugin connected to %s:%d", self.host, self.port)
            return True
        except ImportError:
            logger.error("pymilvus not installed. Run: pip install toolops[milvus]")
            return False
        except Exception as exc:
            logger.error("MilvusPlugin connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        try:
            from pymilvus import connections  # type: ignore[import-untyped]

            connections.disconnect(alias="default")
        except Exception:
            pass
        self._connected = False

    # ── Collection management ─────────────────────────────────

    def create_collection(self, name: str, dim: int) -> bool:
        """Create a Milvus collection with a float vector field."""
        try:
            from pymilvus import (  # type: ignore[import-untyped]
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                utility,
            )

            if utility.has_collection(name):
                logger.debug("Collection '%s' already exists", name)
                return True

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="payload", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields=fields, description=f"ToolOps collection {name}")
            col = Collection(name=name, schema=schema)
            # Create IVF_FLAT index for ANN search
            col.create_index(
                field_name="vector",
                index_params={"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
            )
            self._collections[name] = col
            logger.info("Collection '%s' created (dim=%d)", name, dim)
            return True
        except Exception as exc:
            logger.error("create_collection failed: %s", exc)
            return False

    def delete_collection(self, name: str) -> bool:
        """Drop a Milvus collection."""
        try:
            from pymilvus import utility  # type: ignore[import-untyped]

            if not utility.has_collection(name):
                return False
            utility.drop_collection(name)
            self._collections.pop(name, None)
            return True
        except Exception as exc:
            logger.error("delete_collection failed: %s", exc)
            return False

    def list_collections(self) -> list[str]:
        """Return all Milvus collection names."""
        try:
            from pymilvus import utility  # type: ignore[import-untyped]

            return utility.list_collections()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.error("list_collections failed: %s", exc)
            return []

    # ── Data operations ───────────────────────────────────────

    def _get_collection(self, name: str) -> Any:
        """Load a collection into memory and return it."""
        from pymilvus import Collection  # type: ignore[import-untyped]

        if name not in self._collections:
            self._collections[name] = Collection(name)
        col = self._collections[name]
        col.load()
        return col

    def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, object]],
    ) -> list[str]:
        """Insert vectors and metadata into a Milvus collection."""
        try:
            ids = [str(uuid.uuid4()) for _ in vectors]
            col = self._get_collection(collection)
            col.insert([ids, vectors, metadata])
            col.flush()
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
        """Run ANN search in a Milvus collection."""
        try:
            col = self._get_collection(collection)
            results = col.search(
                data=[query_vector],
                anns_field="vector",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["payload"],
            )
            output: list[dict[str, object]] = []
            for hit in results[0]:
                output.append(
                    {
                        "id": hit.id,
                        "score": hit.score,
                        "metadata": hit.entity.get("payload", {}),
                    }
                )
            return output
        except Exception as exc:
            logger.error("search failed: %s", exc)
            return []

    def delete(self, collection: str, ids: list[str]) -> bool:
        """Delete vectors by ID from a Milvus collection."""
        try:
            col = self._get_collection(collection)
            id_list = '", "'.join(ids)
            col.delete(expr=f'id in ["{id_list}"]')
            return True
        except Exception as exc:
            logger.error("delete failed: %s", exc)
            return False
