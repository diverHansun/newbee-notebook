"""
Newbee Notebook - Session Service

Application service for Session operations.
"""

from typing import Optional, Tuple, List
import logging

from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.entities.notebook import MAX_SESSIONS_PER_NOTEBOOK
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.generated_image import GeneratedImage
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.repositories.notebook_repository import NotebookRepository
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.repositories.generated_image_repository import (
    GeneratedImageRepository,
)
from newbee_notebook.domain.value_objects.mode_type import ModeType
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend


logger = logging.getLogger(__name__)


class NotebookNotFoundError(Exception):
    """Notebook not found."""
    pass


class SessionNotFoundError(Exception):
    """Session not found."""
    pass


class SessionLimitExceededError(Exception):
    """Session limit exceeded."""
    
    def __init__(self, current_count: int, max_count: int = MAX_SESSIONS_PER_NOTEBOOK):
        self.current_count = current_count
        self.max_count = max_count
        super().__init__(
            f"Session limit exceeded: {current_count}/{max_count}"
        )


class SessionService:
    """
    Application service for Session management.
    
    Responsibilities:
    - CRUD operations for Sessions
    - Session limit enforcement (50 per Notebook)
    """
    
    def __init__(
        self,
        session_repo: SessionRepository,
        notebook_repo: NotebookRepository,
        message_repo: MessageRepository,
        generated_image_repo: GeneratedImageRepository | None = None,
        storage: StorageBackend | None = None,
    ):
        self.session_repo = session_repo
        self.notebook_repo = notebook_repo
        self.message_repo = message_repo
        self.generated_image_repo = generated_image_repo
        self.storage = storage

    def _resolve_storage(self) -> StorageBackend | None:
        if self.storage is not None:
            return self.storage
        try:
            self.storage = get_runtime_storage_backend()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Storage backend unavailable while cleaning generated images: %s",
                exc,
            )
            return None
        return self.storage

    @staticmethod
    def _to_message_image_dict(image: GeneratedImage) -> dict:
        return {
            "image_id": image.image_id,
            "storage_key": image.storage_key,
            "prompt": image.prompt,
            "provider": image.provider,
            "model": image.model,
            "width": image.width,
            "height": image.height,
        }
    
    async def create(
        self,
        notebook_id: str,
        title: Optional[str] = None,
        include_ec_context: bool = False,
    ) -> Session:
        """
        Create a new Session in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            title: Optional session title.
            
        Returns:
            Created Session.
            
        Raises:
            NotebookNotFoundError: If notebook not found.
            SessionLimitExceededError: If limit reached.
        """
        # Check notebook exists
        notebook = await self.notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")
        
        # Check session limit
        current_count = await self.session_repo.count_by_notebook(notebook_id)
        if current_count >= MAX_SESSIONS_PER_NOTEBOOK:
            raise SessionLimitExceededError(current_count)
        
        # Create session
        session = Session(
            notebook_id=notebook_id,
            title=title,
            include_ec_context=include_ec_context,
        )
        result = await self.session_repo.create(session)
        
        # Update notebook session count
        await self.notebook_repo.increment_session_count(notebook_id)
        
        logger.info(
            f"Created session {result.session_id} in notebook {notebook_id} "
            f"({current_count + 1}/{MAX_SESSIONS_PER_NOTEBOOK})"
        )
        
        return result
    
    async def get(self, session_id: str) -> Optional[Session]:
        """
        Get a Session by ID.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            Session if found.
        """
        return await self.session_repo.get(session_id)
    
    async def get_or_raise(self, session_id: str) -> Session:
        """
        Get a Session by ID or raise error.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            Session instance.
            
        Raises:
            SessionNotFoundError: If not found.
        """
        session = await self.session_repo.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return session
    
    async def list_by_notebook(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Session], int]:
        """
        List Sessions in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            limit: Maximum number of sessions.
            offset: Number of sessions to skip.
            
        Returns:
            Tuple of (sessions, total_count).
        """
        # Check notebook exists
        notebook = await self.notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")
        
        sessions = await self.session_repo.list_by_notebook(
            notebook_id, limit=limit, offset=offset
        )
        total = await self.session_repo.count_by_notebook(notebook_id)
        
        return sessions, total

    async def list_messages(
        self,
        session_id: str,
        modes: Optional[List[ModeType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Message], int]:
        """List session messages with optional mode filtering."""
        await self.get_or_raise(session_id)
        messages = await self.message_repo.list_by_session(
            session_id=session_id,
            modes=modes,
            limit=limit,
            offset=offset,
        )
        total = await self.message_repo.count_by_session(
            session_id=session_id,
            modes=modes,
        )
        return messages, total

    async def list_message_images(
        self,
        session_id: str,
        message_ids: List[int],
    ) -> dict[int, list[dict]]:
        if not message_ids or self.generated_image_repo is None:
            return {}
        images = await self.generated_image_repo.list_by_message_ids(
            session_id=session_id,
            message_ids=message_ids,
        )
        grouped: dict[int, list[dict]] = {}
        for image in images:
            if image.message_id is None:
                continue
            grouped.setdefault(int(image.message_id), []).append(
                self._to_message_image_dict(image)
            )
        return grouped
    
    async def get_latest(self, notebook_id: str) -> Optional[Session]:
        """
        Get the most recently updated Session in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Latest session or None.
            
        Raises:
            NotebookNotFoundError: If notebook not found.
        """
        notebook = await self.notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")
        
        return await self.session_repo.get_latest_by_notebook(notebook_id)
    
    async def delete(self, session_id: str) -> bool:
        """
        Delete a Session.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            True if deleted.
            
        Raises:
            SessionNotFoundError: If not found.
        """
        session = await self.get_or_raise(session_id)
        notebook_id = session.notebook_id

        if self.generated_image_repo is not None:
            storage = self._resolve_storage()
            if storage is not None:
                images = await self.generated_image_repo.list_by_session(session_id)
                removed_files = 0
                for image in images:
                    if not image.storage_key:
                        continue
                    try:
                        await storage.delete_file(image.storage_key)
                        removed_files += 1
                    except FileNotFoundError:
                        logger.warning(
                            "Generated image already missing during session cleanup: %s",
                            image.storage_key,
                        )
                if removed_files > 0:
                    logger.info(
                        "Removed %d generated image file(s) for session %s",
                        removed_files,
                        session_id,
                    )

        # Delete session (messages and references cascade)
        result = await self.session_repo.delete(session_id)
        
        if result:
            # Update notebook session count
            await self.notebook_repo.increment_session_count(notebook_id, -1)
            logger.info(f"Deleted session: {session_id}")
        
        return result
    
