"""
Newbee Notebook - Notebook Context

Manages the document context for a Notebook, providing document IDs
for RAG retrieval filtering.
"""

from typing import List, Optional, Set
import logging

from newbee_notebook.domain.entities.notebook import Notebook
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.repositories.notebook_repository import NotebookRepository
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.reference_repository import NotebookDocumentRefRepository


logger = logging.getLogger(__name__)


class NotebookContext:
    """
    Manages the retrieval context for a Notebook.
    
    This class is responsible for:
    - Collecting all document IDs accessible by a Notebook
    - Providing these IDs to the retriever for filtering
    - Caching document IDs for performance
    
    Usage:
        context = NotebookContext(notebook_id, notebook_repo, document_repo, ref_repo)
        await context.load()
        
        # Get document IDs for RAG filtering
        doc_ids = context.document_ids
        
        # Use in retrieval
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    value=doc_ids,
                    operator=FilterOperator.IN
                )
            ]
        )
    """
    
    def __init__(
        self,
        notebook_id: str,
        notebook_repo: NotebookRepository,
        document_repo: DocumentRepository,
        ref_repo: NotebookDocumentRefRepository,
    ):
        self._notebook_id = notebook_id
        self._notebook_repo = notebook_repo
        self._document_repo = document_repo
        self._ref_repo = ref_repo
        
        self._notebook: Optional[Notebook] = None
        self._owned_documents: List[Document] = []
        self._referenced_documents: List[Document] = []
        self._document_ids: Set[str] = set()
        self._loaded = False
    
    @property
    def notebook_id(self) -> str:
        """Get the Notebook ID."""
        return self._notebook_id
    
    @property
    def notebook(self) -> Optional[Notebook]:
        """Get the loaded Notebook entity."""
        return self._notebook
    
    @property
    def document_ids(self) -> List[str]:
        """
        Get all document IDs accessible by this Notebook.
        
        This includes:
        - Documents owned by the Notebook
        - Documents referenced from Library
        
        Returns:
            List of document UUIDs as strings.
        """
        return list(self._document_ids)
    
    @property
    def document_count(self) -> int:
        """Get the total number of accessible documents."""
        return len(self._document_ids)
    
    @property
    def is_loaded(self) -> bool:
        """Check if context has been loaded."""
        return self._loaded
    
    async def load(self) -> None:
        """
        Load the Notebook context from database.
        
        This retrieves:
        - The Notebook entity
        - Documents owned by the Notebook
        - Document references from Library
        
        Raises:
            ValueError: If Notebook not found.
        """
        # Load notebook
        self._notebook = await self._notebook_repo.get(self._notebook_id)
        if not self._notebook:
            raise ValueError(f"Notebook not found: {self._notebook_id}")
        
        # Load owned documents
        if self._document_repo:
            self._owned_documents = await self._document_repo.list_by_notebook(
                self._notebook_id, limit=1000
            )
        
        # Load referenced documents
        if self._ref_repo:
            refs = await self._ref_repo.list_by_notebook(self._notebook_id)
            ref_doc_ids = [ref.document_id for ref in refs]
            
            if ref_doc_ids and self._document_repo:
                self._referenced_documents = await self._document_repo.get_batch(
                    ref_doc_ids
                )
        
        # Collect all document IDs
        self._document_ids = set()
        for doc in self._owned_documents:
            self._document_ids.add(doc.document_id)
        for doc in self._referenced_documents:
            self._document_ids.add(doc.document_id)
        
        self._loaded = True
        
        logger.info(
            f"Loaded NotebookContext for {self._notebook_id}: "
            f"{len(self._owned_documents)} owned, "
            f"{len(self._referenced_documents)} referenced, "
            f"{len(self._document_ids)} total documents"
        )
    
    async def refresh(self) -> None:
        """Refresh the context by reloading from database."""
        self._loaded = False
        await self.load()
    
    def get_owned_document_ids(self) -> List[str]:
        """Get IDs of documents owned by the Notebook."""
        return [doc.document_id for doc in self._owned_documents]
    
    def get_referenced_document_ids(self) -> List[str]:
        """Get IDs of documents referenced from Library."""
        return [doc.document_id for doc in self._referenced_documents]
    
    def has_document(self, document_id: str) -> bool:
        """Check if a document is accessible in this Notebook."""
        return document_id in self._document_ids


class NotebookContextManager:
    """
    Factory for creating and caching NotebookContext instances.
    
    Usage:
        manager = NotebookContextManager(notebook_repo, document_repo, ref_repo)
        
        # Get context for a notebook (loads if not cached)
        context = await manager.get_context(notebook_id)
        
        # Invalidate cache when documents change
        manager.invalidate(notebook_id)
    """
    
    def __init__(
        self,
        notebook_repo: NotebookRepository,
        document_repo: DocumentRepository = None,
        ref_repo: NotebookDocumentRefRepository = None,
    ):
        self._notebook_repo = notebook_repo
        self._document_repo = document_repo
        self._ref_repo = ref_repo
        self._cache: dict[str, NotebookContext] = {}
    
    async def get_context(self, notebook_id: str) -> NotebookContext:
        """
        Get or create a NotebookContext.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Loaded NotebookContext instance.
        """
        if notebook_id not in self._cache:
            context = NotebookContext(
                notebook_id,
                self._notebook_repo,
                self._document_repo,
                self._ref_repo,
            )
            await context.load()
            self._cache[notebook_id] = context
        
        return self._cache[notebook_id]
    
    def invalidate(self, notebook_id: str) -> None:
        """
        Invalidate cached context for a notebook.
        
        Call this when documents are added, removed, or references change.
        
        Args:
            notebook_id: Notebook unique identifier.
        """
        if notebook_id in self._cache:
            del self._cache[notebook_id]
            logger.debug(f"Invalidated context cache for notebook: {notebook_id}")
    
    def invalidate_all(self) -> None:
        """Invalidate all cached contexts."""
        self._cache.clear()
        logger.debug("Invalidated all context caches")


