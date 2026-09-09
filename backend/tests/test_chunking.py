"""Hierarchical parent/child chunking tests."""
from app.rag.chunking import chunk_document
from app.rag.models import Document, DocumentMetadata


def _menu_doc(content):
    return Document(
        document_id="doc1",
        content=content,
        metadata=DocumentMetadata(
            document_id="doc1",
            source="menu.md",
            title="Menu",
            document_type="menu",
            topic="drinks",
        ),
    )


def test_headings_become_parent_blocks():
    doc = _menu_doc(
        "# Hot\n\n## Espresso\n\nA shot.\n\n## Latte\n\nMilk and espresso.\n"
    )
    h = chunk_document(doc)
    assert len(h.parents) == 2
    headings = {p.metadata.heading for p in h.parents}
    assert headings == {"Espresso", "Latte"}


def test_heading_paths_are_preserved():
    doc = _menu_doc("# Drinks\n\n## Cold\n\n### Cold Brew\n\nSlow steep.\n")
    h = chunk_document(doc)
    assert h.parents[0].metadata.heading_path == ["Drinks", "Cold", "Cold Brew"]


def test_children_link_to_parents():
    doc = _menu_doc("## Espresso\n\nA concentrated shot.\n\nStrong and bold.\n")
    h = chunk_document(doc)
    assert len(h.parents) == 1
    parent = h.parents[0]
    assert all(c.parent_id == parent.chunk_id for c in h.children)
    assert len(h.children) >= 1


def test_child_tokens_stay_within_bounds():
    long_body = "\n\n".join(
        f"Paragraph {i}: " + "smooth coffee notes " * 60 for i in range(8)
    )
    doc = _menu_doc(f"## Long Section\n\n{long_body}\n")
    h = chunk_document(doc)

    # Parents may exceed a single bound (sections deliberately split into
    # parent-sized blocks) — assert the pipeline produced parents.
    assert len(h.parents) >= 1

    from app.config import CHILD_CHUNK_TOKENS_MAX

    # Average chars/token estimate is heuristic; allow a tolerance so long
    # sentence-grouping does not trip over the estimate.
    limit = CHILD_CHUNK_TOKENS_MAX * 1.15
    for child in h.children:
        approx_tokens = len(child.content) / 4
        assert approx_tokens <= limit, child.content[:60]


def test_metadata_preserved_on_all_chunks():
    doc = _menu_doc("# Drinks\n\n## Mocha\n\nChocolate and espresso.\n")
    h = chunk_document(doc)
    for chunk in h.parents + h.children:
        meta = chunk.metadata
        assert meta.document_id == "doc1"
        assert meta.source == "menu.md"
        assert meta.title == "Menu"
        assert meta.document_type == "menu"
        assert meta.topic == "drinks"


def test_deterministic_ids_with_default_helper():
    doc = _menu_doc("## Espresso\n\nA shot.\n")
    h1 = chunk_document(doc)
    h2 = chunk_document(doc)
    assert [p.chunk_id for p in h1.parents] == [p.chunk_id for p in h2.parents]
    assert [c.chunk_id for c in h1.children] == [c.chunk_id for c in h2.children]


def test_parent_bounds_respected():
    """A subsection sized over the parent cap is split at paragraph
    boundaries into parent-sized blocks (children still link to their parent).
    """
    huge_paragraph = "word " * 4000  # ~2000 tokens (over the 1200 cap)
    doc = _menu_doc(f"## Big\n\n{huge_paragraph}\n")
    h = chunk_document(doc)

    from app.config import PARENT_CHUNK_TOKENS_MAX

    assert len(h.parents) >= 2
    for parent in h.parents:
        assert len(parent.content) / 4 <= PARENT_CHUNK_TOKENS_MAX * 1.15