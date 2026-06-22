"""Processing result models.

Defines :class:`ProcessingResult`, returned by the pipeline to describe the
outcome of processing a document, and :class:`ProcessingStatistics`, which
captures summary metrics (Requirement 12).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from smart_pdf_scanner.models.document import Document


class ProcessingStatistics(BaseModel):
    """Summary statistics gathered during processing.

    Attributes:
        total_pages: Total number of pages in the source document.
        pages_processed: Number of pages successfully processed.
        elements_detected: Total elements detected across all pages.
        tables_extracted: Number of tables extracted.
        images_extracted: Number of images extracted.
        processing_time_seconds: Wall-clock processing time in seconds.
        start_time: Timestamp processing started.
        end_time: Timestamp processing finished.
    """

    total_pages: int = Field(ge=0)
    pages_processed: int = Field(ge=0)
    elements_detected: int = Field(ge=0)
    tables_extracted: int = Field(ge=0)
    images_extracted: int = Field(ge=0)
    processing_time_seconds: float = Field(ge=0.0)
    start_time: datetime
    end_time: datetime


class ProcessingResult(BaseModel):
    """The outcome of running the pipeline on a document.

    Attributes:
        success: Whether processing completed successfully.
        document: The processed document, if available.
        markdown_path: Path to the generated Markdown output, if written.
        assets_folder: Folder containing extracted assets, if any.
        warnings: Non-fatal warnings collected during processing.
        errors: Errors collected during processing.
        statistics: Summary processing statistics.
    """

    success: bool
    document: Document | None = None
    markdown_path: Path | None = None
    assets_folder: Path | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    statistics: ProcessingStatistics
