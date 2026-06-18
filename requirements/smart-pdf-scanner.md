# Smart PDF Scanner — Raw Requirements (Updated)

## 1. General Purpose

The service is intended to convert PDF documents into a structured machine-readable representation in **Markdown** format while preserving the semantic structure of the document, the visual organization of content, and the relationships between elements.

The key goal is correct processing of **complex layouts**, not just text extraction.

The service must work with:

- PDFs with embedded text  
- scanned documents (image-based PDF)  
- hybrid documents  

Maximum supported PDF size: **up to 150 MB**.

---

## 2. Core Functional Capabilities

### 2.1 Text Extraction

The service must:

- extract all text without loss of meaning
- correctly read:
  - multi-column layouts
  - non-standard fonts
  - artistic fonts
  - handwritten text (where possible)
  - text over images
- correctly reconstruct reading order

Priority is **structural and semantic fidelity**, not processing speed.

---

### 2.2 Understanding Document Structure

The system must automatically detect and reconstruct the logical structure:

#### Text hierarchy
- part
- chapter
- section
- subsection
- paragraph
- subparagraph

#### Relationships
- which heading belongs to which text block
- nesting of blocks
- reading sequence
- page numbers for each block

#### Table of contents
- detect the table of contents
- link TOC entries to corresponding document sections

---

### 2.3 Layout Recognition

The system must identify:

- text blocks
- columns
- sidebars
- footnotes
- captions
- lists
- highlighted elements
- formulas (as separate blocks)
- decorative elements (optionally ignored)

### Element Coordinates

For each element, the system must store:

- coordinates on the page
- page number
- element type

This is required for:

- debugging
- validation of recognition correctness
- visualization

---

### 2.4 Recognition Visualization

The system must support visualization including:

- page preview
- overlay of transparent colored bounding boxes
- color coding by element type (text, table, image, etc.)

This is required for:

- quality control
- model debugging
- manual validation

---

### 2.5 Media Content Handling

The system must detect and classify:

- illustrations
- photographs
- diagrams
- charts
- graphs
- tables

---

### 2.6 Table Processing

Tables must:

- be recognized as tables (not plain text)
- be converted into Markdown tables
- preserve:
  - rows
  - columns
  - headers
  - merged cells
  - nested headers
  - rotated text
  - complex structures (as fully as possible)

Additionally:

- optional export of tables to CSV (stored in the assets folder)

---

### 2.7 Illustration and Graphics Processing

For each visual element:

1. save the image file
2. insert a link to it in the Markdown
3. insert an automatically generated textual description

The description must include:

- image type
- content
- meaning (if possible)
- relation to surrounding text
- text detected inside the image (via OCR)

---

### 2.8 Semantic Classification of Images

The system must:

- classify images by type
- distinguish diagram, photograph, chart, illustration, etc.
- incorporate extracted text as part of image semantics

---

### 2.9 Media-to-Text Binding

The system must determine:

- which section an image belongs to
- where it appears in the logical document structure
- image captions
- references to images from text

---

### 2.10 Link Reconstruction

Optionally:

- reconstruct internal document links
- reconstruct external links
- generate a machine-readable link graph

---

## 3. Output Format

### 3.1 Markdown Document

Must contain:

- heading hierarchy
- text blocks
- page numbers
- tables
- image links
- image descriptions
- structured placement of elements

At this stage, **JSON output is not required**.

---

### 3.2 Assets Folder

Contains:

- images
- charts
- diagrams
- extracted media objects
- CSV table exports (optional)

---

### 3.3 Consistency

Markdown must be:

- human-readable
- suitable for RAG / LLM usage
- suitable for reprocessing
- reproducible (idempotency desirable)
- contain sufficient information for later ingestion into a vector database with page mapping

---

## 4. Supported Deployment Modes

### 4.1 Cloud Service
- AWS
- GCP
- Azure
- any cloud platform

---

### 4.2 Local Application with UI

Supported platforms:

- macOS
- Windows
- Linux

Features:

- PDF upload
- result preview
- layout visualization with bounding boxes
- structure view
- export
- quality / speed configuration

---

### 4.3 CLI Utility

Features:

- batch processing
- automation
- pipeline integration
- parameter configuration
- processing modes

---

## 5. Performance and Resources

### 5.1 Local Execution

Must run on an average working laptop:

approximate baseline:

- 16 GB RAM
- CPU-only environment
- GPU optional

Offline mode is desirable but not top priority.

---

### 5.2 Streaming Processing

Supported only if it:

- improves UX
- improves performance
- does not reduce structural fidelity

---

### 5.3 Scalability

The system must:

- process large documents (up to 150 MB)
- support batch processing
- scale horizontally in the cloud

---

## 6. LLM Usage

- LLM usage is expected in most cases (up to ~90%)
- fallback strategy allowed: deterministic methods first, LLM when uncertain
- token usage must be minimized
- LLM should be used only where reasoning is required

---

## 7. Operating Cost

Critically important:

- minimize LLM token usage
- minimize cloud compute usage
- use deterministic methods where possible
- cache results
- support quality modes

---

### Possible Processing Modes

- fast (layout + OCR)
- balanced
- high fidelity (maximum reasoning)
- offline only

---

## 8. UX Requirements

The user must be able to:

- upload a PDF
- choose processing mode
- receive results
- download Markdown
- download assets
- view recognition visualization

---

## 9. Reliability

The system must:

- not crash on complex documents
- support partial processing
- generate warnings
- log issues

---

## 10. Extensibility

The system must allow:

- adding new OCR engines
- adding new layout models
- switching LLM providers
- adding post-processing plugins

---

## 11. Result Quality Priorities

1. correct structure
2. correct reading order
3. correct media binding
4. text completeness
5. OCR accuracy
6. Markdown aesthetics

---

## 12. Quality Metrics (Preliminary Proposal)

A composite quality score should include:

### Structure Accuracy
- correctness of heading hierarchy
- correct block nesting
- correct table of contents recognition

### Layout Consistency
- correct reading order
- correct column segmentation
- absence of overlapping blocks

### OCR Accuracy
- percentage of correctly recognized text
- handwritten text recognition accuracy
- correctness of text extracted from images

### Table Fidelity
- structural correctness
- preservation of merged cells
- similarity to original

### Media Binding Accuracy
- correct attachment of media to text
- description correctness
- link correctness

### Page Mapping Accuracy
- correctness of mapping between blocks and page numbers