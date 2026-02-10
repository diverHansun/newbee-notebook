"""
MediMind Agent - SQLAlchemy ORM Models

Database table definitions using SQLAlchemy ORM.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid
from medimind_agent.domain.value_objects.mode_type import ModeType, MessageRole


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class LibraryModel(Base):
    """Library table - singleton document storage."""
    __tablename__ = "library"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now,
        onupdate=datetime.now
    )
    
    # Relationships
    documents = relationship("DocumentModel", back_populates="library")


class NotebookModel(Base):
    """Notebook table."""
    __tablename__ = "notebooks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now,
        onupdate=datetime.now
    )
    
    # Relationships
    documents = relationship("DocumentModel", back_populates="notebook")
    sessions = relationship(
        "SessionModel", 
        back_populates="notebook",
        cascade="all, delete-orphan"
    )
    references = relationship(
        "NotebookDocumentRefModel",
        back_populates="notebook",
        cascade="all, delete-orphan"
    )


class DocumentModel(Base):
    """Document table."""
    __tablename__ = "documents"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    library_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("library.id"),
        nullable=True
    )
    notebook_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id"),
        nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content_format: Mapped[str] = mapped_column(String(50), default="markdown")
    content_size: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stage_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now,
        onupdate=datetime.now
    )
    
    # Relationships
    library = relationship("LibraryModel", back_populates="documents")
    notebook = relationship("NotebookModel", back_populates="documents")
    
    __table_args__ = (
        CheckConstraint(
            "(library_id IS NULL) <> (notebook_id IS NULL)",
            name="check_document_owner"
        ),
    )


class SessionModel(Base):
    """Session table."""
    __tablename__ = "sessions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now,
        onupdate=datetime.now
    )
    
    # Relationships
    notebook = relationship("NotebookModel", back_populates="sessions")
    references = relationship(
        "ReferenceModel",
        back_populates="session",
        cascade="all, delete-orphan"
    )


class NotebookDocumentRefModel(Base):
    """Notebook-Document reference table (soft links)."""
    __tablename__ = "notebook_document_refs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationships
    notebook = relationship("NotebookModel", back_populates="references")
    document = relationship("DocumentModel")
    
    __table_args__ = (
        UniqueConstraint("notebook_id", "document_id", name="uq_notebook_document"),
    )


class ReferenceModel(Base):
    """Reference table for citation tracking."""
    __tablename__ = "references"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False
    )
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )
    quoted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_source_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationships
    session = relationship("SessionModel", back_populates="references")
    document = relationship("DocumentModel")


class MessageModel(Base):
    """Message table storing conversation history."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


