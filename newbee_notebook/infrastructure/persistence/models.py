"""
Newbee Notebook - SQLAlchemy ORM Models

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
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid


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
    notes = relationship(
        "NoteModel",
        back_populates="notebook",
        cascade="all, delete-orphan",
    )
    diagrams = relationship(
        "DiagramModel",
        back_populates="notebook",
        cascade="all, delete-orphan",
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
    marks = relationship(
        "MarkModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    
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
    compaction_boundary_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    include_ec_context: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)



class AppSettingModel(Base):
    """Application settings key-value overrides."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class MarkModel(Base):
    """Reader mark anchored to a document character offset."""

    __tablename__ = "marks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    anchor_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    context_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    document = relationship("DocumentModel", back_populates="marks")
    note_refs = relationship(
        "NoteMarkRefModel",
        back_populates="mark",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("char_offset >= 0", name="ck_marks_char_offset_nonnegative"),
        Index("idx_marks_document_id", "document_id"),
        Index("idx_marks_created_at", "created_at"),
    )


class NoteModel(Base):
    """Notebook note stored as plain text content."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    notebook = relationship("NotebookModel", back_populates="notes")
    document_tags = relationship(
        "NoteDocumentTagModel",
        back_populates="note",
        cascade="all, delete-orphan",
    )
    mark_refs = relationship(
        "NoteMarkRefModel",
        back_populates="note",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_notes_notebook_id", "notebook_id"),
        Index("idx_notes_updated_at", "updated_at"),
    )


class NoteDocumentTagModel(Base):
    """Explicit document associations for notes."""

    __tablename__ = "note_document_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    note = relationship("NoteModel", back_populates="document_tags")
    document = relationship("DocumentModel")

    __table_args__ = (
        UniqueConstraint("note_id", "document_id", name="uq_note_document_tag"),
        Index("idx_note_document_tags_note_id", "note_id"),
        Index("idx_note_document_tags_document_id", "document_id"),
    )


class NoteMarkRefModel(Base):
    """Parsed mark references extracted from note content."""

    __tablename__ = "note_mark_refs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    mark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marks.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    note = relationship("NoteModel", back_populates="mark_refs")
    mark = relationship("MarkModel", back_populates="note_refs")

    __table_args__ = (
        UniqueConstraint("note_id", "mark_id", name="uq_note_mark_ref"),
        Index("idx_note_mark_refs_note_id", "note_id"),
        Index("idx_note_mark_refs_mark_id", "mark_id"),
    )


class DiagramModel(Base):
    """Notebook-scoped diagram metadata."""

    __tablename__ = "diagrams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    diagram_type: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    content_path: Mapped[str] = mapped_column(Text, nullable=False)
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    node_positions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    notebook = relationship("NotebookModel", back_populates="diagrams")

    __table_args__ = (
        CheckConstraint(
            "format IN ('reactflow_json', 'mermaid')",
            name="ck_diagrams_format",
        ),
        Index("idx_diagrams_notebook_id", "notebook_id"),
        Index("idx_diagrams_document_ids", "document_ids", postgresql_using="gin"),
    )
