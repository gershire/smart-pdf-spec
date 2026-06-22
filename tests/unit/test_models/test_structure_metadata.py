"""Unit tests for structure and metadata models (task 1.5)."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from smart_pdf_scanner.models.elements import BoundingBox, Heading
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.structure import (
    DocumentStructure,
    Link,
    LinkType,
    TableOfContents,
    TOCEntry,
)


def _heading() -> Heading:
    return Heading(
        element_id="h1",
        bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        page_number=0,
        text="Intro",
        level=1,
    )


def test_link_type_values() -> None:
    assert LinkType.INTERNAL.value == "internal"
    assert LinkType.EXTERNAL.value == "external"


def test_link_requires_valid_type() -> None:
    link = Link(source_element_id="e1", target="https://example.com", link_type="external")
    assert link.link_type is LinkType.EXTERNAL
    with pytest.raises(ValidationError):
        Link(source_element_id="e1", target="x", link_type="bogus")


def test_toc_entry_constraints() -> None:
    entry = TOCEntry(title="Chapter 1", page_number=2, level=1)
    assert entry.linked_heading_id is None
    with pytest.raises(ValidationError):
        TOCEntry(title="bad", page_number=1, level=0)


def test_table_of_contents_defaults_empty() -> None:
    toc = TableOfContents()
    assert toc.entries == []


def test_document_structure_defaults() -> None:
    structure = DocumentStructure()
    assert structure.headings == []
    assert structure.toc is None
    assert structure.reading_order == []
    assert structure.links == []


def test_document_structure_with_content() -> None:
    structure = DocumentStructure(
        headings=[_heading()],
        toc=TableOfContents(entries=[TOCEntry(title="Intro", page_number=0, level=1)]),
        reading_order=["h1", "t1"],
        links=[Link(source_element_id="t1", target="#h1", link_type=LinkType.INTERNAL)],
    )
    restored = DocumentStructure.model_validate(json.loads(structure.model_dump_json()))
    assert restored == structure
    assert restored.headings[0].level == 1


def test_metadata_optional_fields_default_none() -> None:
    meta = DocumentMetadata(page_count=3, file_size_bytes=2048)
    assert meta.title is None
    assert meta.creation_date is None


def test_metadata_full_round_trip() -> None:
    meta = DocumentMetadata(
        title="Report",
        author="Jane",
        creation_date=datetime(2024, 1, 2, 3, 4, 5),
        page_count=10,
        file_size_bytes=999,
    )
    restored = DocumentMetadata.model_validate(json.loads(meta.model_dump_json()))
    assert restored == meta


def test_metadata_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        DocumentMetadata(page_count=-1, file_size_bytes=10)
