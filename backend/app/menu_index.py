"""Explicit menu indexing into Qdrant for semantic retrieval.

This is a deliberate setup/maintenance operation — never triggered by a chat
request. Firestore remains the source of truth; the vector store is rebuilt
from the canonical menu documents.

Usage:
    python -m app.menu_index                       # index the canonical Firestore menu
    python -m app.menu_index --json data/menu.json # index validated local menu.json
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.menu_ingestion import load_menu, validate_menu
from app.rag.menu import MenuIndexer, MenuIndexingError, MenuIndexingResult

logger = logging.getLogger(__name__)


def _firestore_items() -> list[dict]:
    from app.repositories.menu import list_menu_items

    return list_menu_items()


def run(*, source: str = "firestore", path: str | None = None) -> MenuIndexingResult:
    """Index the selected menu source and return the indexing result."""
    if source == "json":
        items = load_menu(path)
        validate_menu(items)
    else:
        items = _firestore_items()

    if not items:
        raise MenuIndexingError("No menu items found to index.")

    return MenuIndexer().index(items)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index the Grounded menu into Qdrant for semantic retrieval."
    )
    parser.add_argument(
        "--json",
        dest="path",
        metavar="PATH",
        help="Index a validated local menu JSON file instead of the Firestore menu.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args()
    try:
        result = run(source="json" if args.path else "firestore", path=args.path)
        print(
            f"Done — indexed {result.document_count} menu items "
            f"({result.vector_count} vectors, dimension {result.vector_size})."
        )
    except MenuIndexingError as exc:
        print(f"Indexing failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Indexing failed")
        print(f"Indexing failed: {exc}", file=sys.stderr)
        sys.exit(1)