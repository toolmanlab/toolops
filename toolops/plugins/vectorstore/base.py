"""Abstract base class for vector store plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod


class VectorStorePlugin(ABC):
    """Unified interface that every vector store adapter must implement.

    Implement this ABC to add a new vector store backend.
    All methods are synchronous; wrap in asyncio.to_thread for async callers.
    """

    # ── Lifecycle ─────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the vector store.

        Returns:
            True if connection succeeded, False otherwise.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection and release resources."""

    # ── Collection management ─────────────────────────────────

    @abstractmethod
    def create_collection(self, name: str, dim: int) -> bool:
        """Create a new vector collection / index.

        Args:
            name: Collection name (must be unique).
            dim:  Embedding dimensionality.

        Returns:
            True on success or if collection already exists.
        """

    @abstractmethod
    def delete_collection(self, name: str) -> bool:
        """Drop a collection and all its vectors.

        Args:
            name: Collection name to delete.

        Returns:
            True on success, False if collection not found.
        """

    @abstractmethod
    def list_collections(self) -> list[str]:
        """Return names of all existing collections."""

    # ── Data operations ───────────────────────────────────────

    @abstractmethod
    def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, object]],
    ) -> list[str]:
        """Insert vectors with associated metadata.

        Args:
            collection: Target collection name.
            vectors:    List of embedding vectors (each of length ``dim``).
            metadata:   Parallel list of metadata dicts for each vector.

        Returns:
            List of assigned IDs (one per inserted vector).
        """

    @abstractmethod
    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, object]]:
        """Nearest-neighbour search.

        Args:
            collection:   Collection to search in.
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of result dicts, each containing at least
            ``{"id": str, "score": float, "metadata": dict}``.
        """

    @abstractmethod
    def delete(self, collection: str, ids: list[str]) -> bool:
        """Delete specific vectors by ID.

        Args:
            collection: Collection containing the vectors.
            ids:        List of vector IDs to delete.

        Returns:
            True if all IDs were deleted successfully.
        """

    # ── Context-manager support ───────────────────────────────

    def __enter__(self) -> VectorStorePlugin:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
