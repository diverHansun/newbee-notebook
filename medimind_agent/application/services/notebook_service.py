"""
MediMind Agent - Notebook Service

Application service for Notebook operations.
"""

from typing import Optional, Tuple, List
import logging

from medimind_agent.domain.entities.notebook import Notebook, MAX_SESSIONS_PER_NOTEBOOK
from medimind_agent.domain.entities.reference import NotebookDocumentRef
from medimind_agent.domain.entities.document import Document
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.domain.repositories.document_repository import DocumentRepository
from medimind_agent.domain.repositories.session_repository import SessionRepository
from medimind_agent.domain.repositories.reference_repository import NotebookDocumentRefRepository


logger = logging.getLogger(__name__)


class NotebookNotFoundError(Exception):
    """Notebook not found."""
    pass


class DocumentNotFoundError(Exception):
    """Document not found."""
    pass


class DuplicateReferenceError(Exception):
    """Document already referenced."""
    pass


class NotebookService:
    """
    Application service for Notebook management.
    
    Responsibilities:
    - CRUD operations for Notebooks
    - Document reference management
    - Cascade deletion logic
    """
    
    def __init__(
        self,
        notebook_repo: NotebookRepository,
        document_repo: DocumentRepository,
        session_repo: SessionRepository,
        ref_repo: NotebookDocumentRefRepository,
    ):
        self.notebook_repo = notebook_repo
        self.document_repo = document_repo
        self.session_repo = session_repo
        self.ref_repo = ref_repo
    
    async def create(
        self, 
        title: str, 
        description: Optional[str] = None
    ) -> Notebook:
        """
        Create a new Notebook.
        
        Args:
            title: Notebook title.
            description: Optional description.
            
        Returns:
            Created Notebook.
        """
        notebook = Notebook(
            title=title,
            description=description,
        )
        result = await self.notebook_repo.create(notebook)
        logger.info(f"Created notebook: {result.notebook_id}")
        return result
    
    async def get(self, notebook_id: str) -> Optional[Notebook]:
        """
        Get a Notebook by ID.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Notebook if found.
        """
        return await self.notebook_repo.get(notebook_id)
    
    async def get_or_raise(self, notebook_id: str) -> Notebook:
        """
        Get a Notebook by ID or raise error.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Notebook instance.
            
        Raises:
            NotebookNotFoundError: If not found.
        """
        notebook = await self.notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")
        return notebook
    
    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Notebook], int]:
        """
        List all Notebooks.
        
        Args:
            limit: Maximum number of notebooks.
            offset: Number of notebooks to skip.
            
        Returns:
            Tuple of (notebooks, total_count).
        """
        notebooks = await self.notebook_repo.list(limit=limit, offset=offset)
        total = await self.notebook_repo.count()
        return notebooks, total
    
    async def update(
        self,
        notebook_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Notebook:
        """
        Update a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            title: New title (if provided).
            description: New description (if provided).
            
        Returns:
            Updated Notebook.
            
        Raises:
            NotebookNotFoundError: If not found.
        """
        notebook = await self.get_or_raise(notebook_id)
        
        if title is not None:
            notebook.title = title
        if description is not None:
            notebook.description = description
        notebook.touch()
        
        return await self.notebook_repo.update(notebook)
    
    async def delete(self, notebook_id: str) -> bool:
        """
        Delete a Notebook and all related data.
        
        This will delete:
        - All sessions in the notebook
        - All documents owned by the notebook
        - All references from this notebook
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            True if deleted.
            
        Raises:
            NotebookNotFoundError: If not found.
        """
        notebook = await self.get_or_raise(notebook_id)
        
        # Delete references
        ref_count = await self.ref_repo.delete_by_notebook(notebook_id)
        logger.info(f"Deleted {ref_count} references from notebook {notebook_id}")
        
        # Delete owned documents (not Library documents)
        doc_count = await self.document_repo.delete_by_notebook(notebook_id)
        logger.info(f"Deleted {doc_count} documents from notebook {notebook_id}")
        
        # Sessions are deleted by cascade (ON DELETE CASCADE)
        
        # Delete notebook
        result = await self.notebook_repo.delete(notebook_id)
        logger.info(f"Deleted notebook: {notebook_id}")
        
        return result
    
    # =========================================================================
    # Document Reference Management
    # =========================================================================
    
    async def create_reference(
        self,
        notebook_id: str,
        document_id: str,
    ) -> NotebookDocumentRef:
        """
        Create a reference from a Library document to a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            document_id: Library document unique identifier.
            
        Returns:
            Created reference.
            
        Raises:
            NotebookNotFoundError: If notebook not found.
            DocumentNotFoundError: If document not found or not in Library.
            DuplicateReferenceError: If already referenced.
        """
        # Check notebook exists
        await self.get_or_raise(notebook_id)
        
        # Check document exists and is in Library
        document = await self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        if not document.is_library_document:
            raise DocumentNotFoundError(f"Document is not in Library: {document_id}")
        
        # Check not already referenced
        existing = await self.ref_repo.get_by_notebook_and_document(
            notebook_id, document_id
        )
        if existing:
            raise DuplicateReferenceError(
                f"Document {document_id} already referenced in notebook {notebook_id}"
            )
        
        # Create reference
        ref = NotebookDocumentRef(
            notebook_id=notebook_id,
            document_id=document_id,
        )
        result = await self.ref_repo.create(ref)
        logger.info(
            f"Created reference: notebook={notebook_id}, document={document_id}"
        )
        
        return result
    
    async def list_references(
        self,
        notebook_id: str,
    ) -> List[NotebookDocumentRef]:
        """
        List all document references for a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            List of references.
            
        Raises:
            NotebookNotFoundError: If notebook not found.
        """
        await self.get_or_raise(notebook_id)
        return await self.ref_repo.list_by_notebook(notebook_id)
    
    async def delete_reference(
        self,
        notebook_id: str,
        reference_id: str,
    ) -> bool:
        """
        Delete a document reference.
        
        Args:
            notebook_id: Notebook unique identifier.
            reference_id: Reference unique identifier.
            
        Returns:
            True if deleted.
            
        Raises:
            NotebookNotFoundError: If notebook not found.
            ValueError: If reference not found.
        """
        await self.get_or_raise(notebook_id)
        
        ref = await self.ref_repo.get(reference_id)
        if not ref or ref.notebook_id != notebook_id:
            raise ValueError(f"Reference not found: {reference_id}")
        
        result = await self.ref_repo.delete(reference_id)
        logger.info(f"Deleted reference: {reference_id}")
        return result
    
    async def get_all_document_ids(self, notebook_id: str) -> List[str]:
        """
        Get all document IDs accessible by a Notebook.
        
        This includes:
        - Documents owned by the Notebook
        - Documents referenced from Library
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            List of document IDs.
        """
        # Get owned documents
        owned_docs = await self.document_repo.list_by_notebook(notebook_id)
        owned_ids = [doc.document_id for doc in owned_docs]
        
        # Get referenced documents
        refs = await self.ref_repo.list_by_notebook(notebook_id)
        ref_ids = [ref.document_id for ref in refs]
        
        # Combine and deduplicate
        return list(set(owned_ids + ref_ids))


