"""Structure-aware hierarchical parent/child chunking.

Target starting ranges (tunable via config):

    parent chunks: ~600-1200 tokens
    child chunks:  ~150-300 tokens

These bounds are starting points, not immutable. The splitter reads them from
configuration so they can be tuned without code changes.

We prefer actual document structure (headings, sections, paragraphs, lists)
over blind character/N-token splitting:
  - Sections are delimited by heading markers (``#``).
  - Paragraphs are delimited by blank lines.
  - Each section becomes a parent block.
  - A section that exceeds the parent size is split across paragraph
    boundaries into parent-sized blocks.
  - Each parent block is then split into child chunks that stay inside the
    child token bounds, again preferring paragraph boundaries.
"""
from __future__ import annotations

import re
from typing import Callable

from app.config import (
    CHILD_CHUNK_TOKENS_MAX,
    PARENT_CHUNK_TOKENS_MAX,
)
from app.rag.models import (
    ChildChunk,
    Document,
    DocumentMetadata,
    Hierarchy,
    ParentChunk,
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

# Rough token estimate: 4 chars ~ 1 token. Good enough for chunk-size planning.
AVG_CHARS_PER_TOKEN = 4.0


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / AVG_CHARS_PER_TOKEN))


class _Section:
    """A structured block of text captured from the document."""

    def __init__(
        self,
        heading: str,
        heading_path: list[str],
        body: str,
        level: int,
    ):
        self.heading = heading
        self.heading_path = heading_path
        self.body = body.strip()
        self.level = level


def _heading_level(match) -> int:
    return len(match.group(1))


def _split_sections(content: str) -> list[_Section]:
    """Split document content into sections by markdown headings."""
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        body = content.strip()
        return [_Section("", [], body)] if body else []

    sections: list[_Section] = []
    for idx, match in enumerate(matches):
        level = _heading_level(match)
        heading = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        sections.append(_Section(heading, [], body, level))

    # Build heading_path (ancestor chain) for each section while respecting
    # the actual heading levels.
    stack: list[str] = []
    for section in sections:
        while stack and section.level <= len(stack):
            stack.pop()
        if section.heading:
            stack.append(section.heading)
        section.heading_path = list(stack)

    return sections


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paragraphs or ([text.strip()] if text.strip() else [])


def _chunk_to_max(text: str, max_tokens: int) -> list[str]:
    """Split text into pieces each within ``max_tokens``, at sentence
    boundaries, then hard-bound any remaining over-long fragment."""
    if _estimate_tokens(text) <= max_tokens:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if _estimate_tokens(candidate) > max_tokens and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)

    out: list[str] = []
    for piece in pieces:
        if _estimate_tokens(piece) <= max_tokens:
            out.append(piece)
            continue
        # A single sentence still over the cap: hard split.
        chars = int(max_tokens * AVG_CHARS_PER_TOKEN)
        out.extend(piece[i : i + chars] for i in range(0, len(piece), chars))
        if piece.endswith("\n"):
            out[-1] += "\n"
    return out or [text]


def _split_long_paragraph(paragraph: str) -> list[str]:
    """Split a paragraph by sentence boundaries to fit child max tokens."""
    return _chunk_to_max(paragraph, CHILD_CHUNK_TOKENS_MAX)


def _split_parent_blocks(section_body: str) -> list[str]:
    """Split a section into parent-sized blocks.

    Prefers paragraph boundaries; oversized paragraphs are split further at
    sentence boundaries, then smaller pieces are greedily re-grouped to stay
    near the parent cap without exceeding it.
    """
    if _estimate_tokens(section_body) <= PARENT_CHUNK_TOKENS_MAX:
        return [section_body]

    paragraphs = _split_paragraphs(section_body)
    pieces: list[str] = []
    for paragraph in paragraphs:
        pieces.extend(_chunk_to_max(paragraph, PARENT_CHUNK_TOKENS_MAX))

    blocks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}".strip() if current else piece
        if _estimate_tokens(candidate) > PARENT_CHUNK_TOKENS_MAX and current:
            blocks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        blocks.append(current)
    return blocks or [section_body]


def _metadata_for_section(
    base: DocumentMetadata, section: _Section
) -> DocumentMetadata:
    """Return document metadata annotated with the section heading context."""
    return DocumentMetadata(
        document_id=base.document_id,
        source=base.source,
        title=base.title,
        heading=section.heading,
        heading_path=section.heading_path,
        document_type=base.document_type,
        topic=base.topic,
        version=base.version,
    )


def chunk_document(
    document: Document,
    assign_ids: Callable[[str, int, str], str] | None = None,
) -> Hierarchy:
    """Chunk a document into parent and child blocks.

    ``assign_ids`` lets callers control id generation (default: deterministic
    ``<document_id>:<level>:<position>``).
    """
    helper = assign_ids or (
        lambda doc_id, position, level: f"{doc_id}:{level}:{position}"
    )
    meta: DocumentMetadata = document.metadata or DocumentMetadata(
        document_id=document.document_id,
        source=document.metadata.source if document.metadata else "",
    )

    sections = _split_sections(document.content)

    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    for section in sections:
        if not section.body:
            continue

        parent_meta = _metadata_for_section(meta, section)

        parent_position = len(parents)
        for body in _split_parent_blocks(section.body):
            parent_id = helper(document.document_id, len(parents), "parent")
            parents.append(
                ParentChunk(
                    chunk_id=parent_id,
                    parent_id=None,
                    document_id=document.document_id,
                    content=body,
                    position=parent_position,
                    metadata=parent_meta,
                )
            )
            parent_position += 1

            child_position = 0
            for paragraph in _split_paragraphs(body):
                for part in _split_long_paragraph(paragraph):
                    children.append(
                        ChildChunk(
                            chunk_id=helper(
                                document.document_id, len(children), "child"
                            ),
                            parent_id=parent_id,
                            document_id=document.document_id,
                            content=part,
                            position=child_position,
                            metadata=parent_meta,
                        )
                    )
                    child_position += 1

    return Hierarchy(
        document=meta,
        parents=parents,
        children=children,
    )