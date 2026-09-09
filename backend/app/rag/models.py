"""Core data models used across the RAG layer (and the chunking pipeline)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DocumentMetadata(BaseModel):
    """Metadata attached to every ingested document and chunk.

    These fields support document identity, provenance, citation, and
    filtering. Custom extra metadata is allowed (e.g. ``category``/``price``
    for menu items) via ``extra``.
    """

    document_id: str
    source: str
    title: str = ""
    heading: str = ""
    heading_path: list[str] = Field(default_factory=list)
    document_type: str = "unknown"
    topic: str = ""
    version: str = "1"
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A source document to be ingested into the knowledge base."""

    document_id: str
    content: str
    metadata: DocumentMetadata


class Chunk(BaseModel):
    """A single chunk produced by hierarchical chunking.

    Children carry ``parent_id`` so a retrieved child can be expanded to its
    parent block. Parents carry their own ``chunk_id`` and reference children.
    """

    chunk_id: str
    parent_id: str | None = None
    document_id: str
    content: str
    position: int = 0
    metadata: DocumentMetadata
    level: str = "child"  # "parent" | "child"


class ParentChunk(Chunk):
    level: str = "parent"


class ChildChunk(Chunk):
    level: str = "child"
    parent_id: str  # required for children


class Hierarchy(BaseModel):
    """Result of hierarchical chunking for one document."""

    document: DocumentMetadata
    parents: list[ParentChunk] = Field(default_factory=list)
    children: list[ChildChunk] = Field(default_factory=list)

    def parent_of(self, child_id: str) -> ParentChunk | None:
        for parent in self.parents:
            if parent.chunk_id == child_id:
                return parent
        child = next((c for c in self.children if c.chunk_id == child_id), None)
        if child is None or child.parent_id is None:
            return None
        for parent in self.parents:
            if parent.chunk_id == child.parent_id:
                return parent
        return None


class RetrievedChunk(BaseModel):
    """A chunk returned by retrieval, with a relevance score."""

    chunk: Chunk
    score: float
    source: str = ""
    parent: ParentChunk | None = None

    @property
    def text(self) -> str:
        """Prefer expanded parent context when available."""
        if self.parent is not None:
            return self.parent.content
        return self.chunk.content


class Evidence(BaseModel):
    """Assembled evidence passed to the generator.

    ``context`` is the formatted, de-duplicated text used for generation.
    ``citations`` lets the answer include source references.
    """

    context: str
    citations: list[str] = Field(default_factory=list)
    retrieval_count: int = 0
    retrieved_at: str = Field(default_factory=lambda: _now_utc().isoformat())


class IngestionResult(BaseModel):
    """Result of a document ingestion operation."""

    document_id: str
    parent_count: int = 0
    child_count: int = 0
    vector_count: int = 0
    status: str = "ok"