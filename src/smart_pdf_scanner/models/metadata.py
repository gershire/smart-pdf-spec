"""Document metadata model.

Captures the standard PDF document information dictionary fields together with
basic file statistics (Requirement 5). The model uses Pydantic for validation
and JSON serialization.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata describing a source PDF document.

    Attributes:
        title: Document title, if present.
        author: Document author, if present.
        subject: Document subject, if present.
        keywords: Comma-separated keywords, if present.
        creator: Application that created the original document.
        producer: Application that produced the PDF.
        creation_date: Timestamp the document was created.
        modification_date: Timestamp the document was last modified.
        page_count: Total number of pages in the document.
        file_size_bytes: Size of the source file in bytes.
    """

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: datetime | None = None
    modification_date: datetime | None = None
    page_count: int = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
