"""Storage backend abstract base class."""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import BinaryIO


class StorageBackend(ABC):
    """Unified interface for document file storage backends.

    Object keys use POSIX path format: {document_id}/{category}/{filename}
    Examples:
        393f579b-.../original/paper.pdf
        393f579b-.../markdown/content.md
        393f579b-.../assets/images/a267b5...jpg
    """

    @abstractmethod
    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Save a file from a binary stream.

        Returns:
            The stored object key.
        """

    @abstractmethod
    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Save a file from a local filesystem path.

        Returns:
            The stored object key.
        """

    @abstractmethod
    async def get_file(self, object_key: str) -> bytes:
        """Read file content as bytes.

        Raises:
            FileNotFoundError: Object does not exist.
        """

    @abstractmethod
    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        """Read file content as text.

        Raises:
            FileNotFoundError: Object does not exist.
        """

    @abstractmethod
    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        """Get a browser-accessible URL for the file.

        For local backend: returns an API route path.
        For MinIO backend: returns a presigned GET URL.
        """

    @abstractmethod
    async def delete_file(self, object_key: str) -> None:
        """Delete a single file.

        Raises:
            FileNotFoundError: Object does not exist.
        """

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a prefix (e.g. ``{document_id}/``).

        Returns:
            Number of deleted objects.
        """

    @abstractmethod
    async def list_objects(self, prefix: str) -> list[str]:
        """List all object keys under a prefix."""

    @abstractmethod
    async def exists(self, object_key: str) -> bool:
        """Check whether an object exists."""
