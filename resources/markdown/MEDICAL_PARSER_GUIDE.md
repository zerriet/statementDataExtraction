# Medical Invoice Parser - Technical Guide

**Version:** 2.2
**Date:** January 2026
**Purpose:** Learning & System Integration Reference

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Core Components](#4-core-components)
5. [PDF Parsing Deep Dive](#5-pdf-parsing-deep-dive)
6. [Inference Layer](#6-inference-layer)
7. [API Service](#7-api-service)
8. [Data Flow](#8-data-flow)
9. [Template System](#9-template-system)
10. [Integration Guide for Parent Agents](#10-integration-guide-for-parent-agents)
11. [Error Handling & Edge Cases](#11-error-handling--edge-cases)
12. [Testing & Validation](#12-testing--validation)
13. [Deployment](#13-deployment)
14. [Revision History](#14-revision-history)

---

## 1. Overview

### What This Service Does

The Medical Invoice Parser is a **downstream microservice** that extracts structured data from medical invoice PDFs. It is designed to be called by an **upstream agentic framework** (e.g., an LLM-powered agent) as part of an automated claims processing workflow.

### Design Philosophy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DESIGN PRINCIPLES                                │
├─────────────────────────────────────────────────────────────────────────┤
│  1. DEFENSIVE PARSING     │ Treat PDFs as hostile, semi-graphical docs  │
│  2. FAIL TRANSPARENTLY    │ Explicit errors > silent failures          │
│  3. DETERMINISTIC FIRST   │ PyMuPDF extraction before any AI/ML        │
│  4. SEPARATION OF CONCERNS│ Extract vs Infer are separate steps        │
│  5. HUMAN-IN-THE-LOOP     │ Flag uncertain fields for review           │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Gets Extracted vs Inferred

| Extracted (Deterministic Parser) | Inferred (Inference Layer) | External Context (Upstream Agent) |
|----------------------------------|----------------------------|-----------------------------------|
| Invoice number | Benefit category | Employee ID (HR lookup) |
| Visit date | Benefit type | Department (HR lookup) |
| Provider name | Diagnosis code | Claimant email (session) |
| Patient name | | Date of claim |
| Line items | | Attachments (file handling) |
| Subtotal, GST, Total | | |
| Raw diagnosis text | | |

### Inference Layer Responsibility Boundary

The inference layer (added in v2.0) resolves fields that can be determined **from PDF content alone**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RESPONSIBILITY BOUNDARIES                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PARSER + INFERENCE LAYER                UPSTREAM AGENT                     │
│  (can resolve from PDF)                  (needs external context)           │
│                                                                             │
│  ✓ invoiceNumber                         ✓ employeeId (HR lookup)           │
│  ✓ visitDate                             ✓ department (HR lookup)           │
│  ✓ providerName                          ✓ claimant.fullName (session)      │
│  ✓ patientName                           ✓ claimant.email (session)         │
│  ✓ lineItems                             ✓ dateOfClaim (current date)       │
│  ✓ amounts (subtotal, GST, total)        ✓ attachments (file handling)      │
│  ✓ diagnosisRaw                                                             │
│  ✓ benefitType (from keywords/SLM)       ✓ Final validation                 │
│  ✓ benefitCategory (from keywords/SLM)   ✓ HITL prompts                     │
│  ✓ diagnosisCode (from keywords/SLM)     ✓ Submit to Claims API             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        UPSTREAM AGENTIC FRAMEWORK                         │
│                     (Claude, GPT, Custom Agent, etc.)                     │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │    User     │───▶│   Agent     │───▶│  Decision   │                  │
│  │   Request   │    │   Logic     │    │   Engine    │                  │
│  └─────────────┘    └──────┬──────┘    └─────────────┘                  │
│                            │                                             │
└────────────────────────────┼─────────────────────────────────────────────┘
                             │
                             │ HTTP POST /parse
                             │ (PDF file or base64)
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     MEDICAL INVOICE PARSER SERVICE                        │
│                         (This Microservice)                               │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │   FastAPI   │───▶│   Parser    │───▶│   Result    │                  │
│  │  Endpoint   │    │   Engine    │    │  Formatter  │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                                                          │
│  Returns: { extracted, inference_required, metadata }                    │
└──────────────────────────────────────────────────────────────────────────┘
                             │
                             │ JSON Response
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        UPSTREAM AGENT CONTINUES                           │
│                                                                          │
│  1. Receives extracted data                                              │
│  2. Fetches template with keyword mappings (GET /template)               │
│  3. Performs inference on flagged fields                                 │
│  4. Submits complete claim to claims API                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

### Service Component Architecture

```
src/
├── api/
│   ├── __init__.py
│   ├── medical_invoice_api.py      # FastAPI application
│   └── README.md                   # API documentation
│
├── parsers/
│   ├── __init__.py
│   ├── medical_invoice_parser.py   # Core parsing logic
│   └── deterministic_parser.py     # Bank statement parser (reference)
│
├── inference/                      # NEW: Inference layer module
│   ├── __init__.py                 # Module exports
│   ├── config.py                   # InferenceSettings (pydantic-settings)
│   ├── models.py                   # Pydantic models for inference results
│   ├── keyword_matcher.py          # Rule-based keyword matching
│   ├── slm_client.py               # OpenAI GPT-4o-mini client
│   └── inference_service.py        # Orchestrator (keyword → SLM → HITL)
│
└── diagnostics/
    ├── analyze_pdf_coordinates.py  # PDF structure analysis tool
    └── inspect_transaction.py      # Debug tool for PDF inspection

resources/
├── jsonTemplates/
│   ├── claimSubmitTemplate.json    # v1: Basic template
│   └── claimSubmitTemplate2.json   # v2: With keyword mappings for inference
│
├── statements/
│   └── medical_invoice_statements/ # Test invoice PDFs
│
└── markdown/
    └── MEDICAL_PARSER_GUIDE.md     # This document

gui/
└── index.html                      # Test interface

.env.example                        # Configuration template for inference
```

---

## 3. Technology Stack

### Core Dependencies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Runtime language |
| **PyMuPDF** | ≥1.24.5 | PDF text extraction with coordinates |
| **FastAPI** | ≥0.110.0 | REST API framework |
| **Pydantic** | ≥2.2.1 | Data validation & serialization |
| **Pydantic-Settings** | ≥2.2.1 | Configuration management |
| **Uvicorn** | ≥0.30.0 | ASGI server |

### Inference Layer Dependencies (Optional)

| Technology | Version | Purpose |
|------------|---------|---------|
| **OpenAI** | ≥1.30.0 | GPT-4.1-mini SLM client |
| **Instructor** | ≥1.4.0 | Structured LLM outputs with Pydantic |

> **Note:** The inference layer works in **keyword-only mode** without OpenAI dependencies.
> SLM fallback is only used when keyword matching fails AND an API key is configured.

### Why PyMuPDF?

PyMuPDF (also known as `fitz`) was chosen for several key reasons:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PyMuPDF CAPABILITIES                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. COORDINATE EXTRACTION                                               │
│     ─────────────────────                                               │
│     page.get_text("words") returns:                                     │
│     (x0, y0, x1, y1, "text", block_no, line_no, word_no)               │
│                                                                         │
│     This allows position-based column detection without relying         │
│     on fragile text patterns or table detection heuristics.             │
│                                                                         │
│  2. UNICODE HANDLING                                                    │
│     ────────────────────                                                │
│     Automatically resolves ToUnicode CMaps in PDFs.                     │
│     No manual character encoding required.                              │
│                                                                         │
│  3. TEXT LAYER INTEGRITY                                                │
│     ───────────────────────                                             │
│     Can detect if PDF has a text layer or needs OCR.                    │
│     Supports both native PDFs and scanned documents.                    │
│                                                                         │
│  4. PERFORMANCE                                                         │
│     ────────────────                                                    │
│     Written in C with Python bindings.                                  │
│     Fast processing even for large documents.                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why FastAPI?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI BENEFITS                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  • ASYNC SUPPORT        Native async/await for concurrent requests      │
│  • AUTO DOCUMENTATION   Swagger UI at /docs, ReDoc at /redoc           │
│  • TYPE VALIDATION      Pydantic models for request/response           │
│  • FILE UPLOADS         Built-in multipart/form-data handling          │
│  • CORS MIDDLEWARE      Easy cross-origin configuration                │
│  • OPENAPI SPEC         Auto-generated API specification               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Core Components

### 4.1 MedicalInvoiceParser Class

**Location:** `src/parsers/medical_invoice_parser.py`

```python
class MedicalInvoiceParser:
    """
    Defensive parser for medical invoices using PyMuPDF

    Extracts fields that can be directly parsed from invoice PDFs.
    Fields requiring inference are flagged for review.
    """
```

#### Key Methods

| Method | Purpose |
|--------|---------|
| `parse(pdf_path)` | Main entry point - orchestrates extraction |
| `_validate_document(doc)` | Ingestion guard - checks text layer integrity |
| `_group_words_into_lines(words)` | Groups words by Y-coordinate (±3px tolerance) |
| `_extract_invoice_data(text, lines)` | Extracts all fields from document |
| `_extract_invoice_number(text)` | Pattern matching for invoice numbers |
| `_extract_date(text, lines)` | Multi-format date parsing |
| `_extract_provider_name(lines)` | Header text extraction |
| `_extract_patient_name(text, lines)` | Patient identification |
| `_extract_amounts(text)` | Subtotal, GST, Total extraction |
| `_extract_diagnosis_raw(text)` | Raw diagnosis text capture |
| `_extract_line_items(lines)` | Itemized services/medications |
| `_flag_inference_fields(data)` | Marks fields needing inference |

#### Initialization & State

```python
def __init__(self):
    self.warnings = []           # Non-fatal issues encountered
    self.confidence = 1.0        # Starts at 100%, degraded on issues
    self.requires_review = []    # Fields flagged for HITL/inference
```

### 4.2 MedicalInvoiceResult Dataclass

```python
@dataclass
class MedicalInvoiceResult:
    success: bool                      # Extraction succeeded/failed
    data: Dict                         # Extracted invoice data
    confidence: float                  # 0.0-1.0 confidence score
    warnings: List[str]                # Non-fatal warnings
    requires_review: List[str]         # Fields needing inference
    abort_reason: Optional[str]        # Failure reason if success=False

    def to_json(self, source_file: str = None) -> Dict:
        """Export as JSON for upstream framework"""

    def to_json_string(self, source_file: str = None) -> str:
        """Export as formatted JSON string"""
```

### 4.3 Convenience Functions

```python
# Single file parsing
def parse_invoice(pdf_path: str) -> Dict:
    """Returns JSON-serializable dict for upstream framework"""

# Batch processing
def parse_invoice_folder(folder_path: str) -> List[Dict]:
    """Parse all PDFs in a folder"""
```

---

## 5. PDF Parsing Deep Dive

### 5.1 How PDF Text Extraction Works

PDFs store text as **positioned glyphs**, not logical lines. PyMuPDF's `get_text("words")` reconstructs words from these glyphs:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PDF INTERNAL STRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PDF Content Stream:                                                    │
│  ──────────────────                                                     │
│  BT                           % Begin Text                              │
│  /F1 12 Tf                    % Font: F1, Size: 12pt                    │
│  100 700 Td                   % Position: x=100, y=700                  │
│  (Invoice) Tj                 % Draw "Invoice"                          │
│  50 0 Td                      % Move right 50 units                     │
│  (Number:) Tj                 % Draw "Number:"                          │
│  ET                           % End Text                                │
│                                                                         │
│  PyMuPDF Output:                                                        │
│  ───────────────                                                        │
│  [                                                                      │
│    (100.0, 700.0, 145.0, 712.0, "Invoice", 0, 0, 0),                   │
│    (150.0, 700.0, 200.0, 712.0, "Number:", 0, 0, 1),                   │
│  ]                                                                      │
│                                                                         │
│  Format: (x0, y0, x1, y1, text, block, line, word)                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Y-Coordinate Line Grouping

Words on the same visual line may have slightly different Y-coordinates due to PDF rendering. We group words within a **3-pixel tolerance**:

```python
def _group_words_into_lines(self, words):
    lines_dict = {}

    for word in words:
        x0, y0, x1, y1, text = word[:5]

        # Find existing line with similar Y
        line_key = None
        for existing_y in lines_dict.keys():
            if abs(existing_y - y0) < 3:  # 3px tolerance
                line_key = existing_y
                break

        if line_key is None:
            line_key = y0
            lines_dict[line_key] = []

        lines_dict[line_key].append({
            "text": text,
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1
        })

    # Sort lines by Y, words within lines by X
    return sorted_lines
```

**Visual Example:**

```
Y=100.0  ┌──────────────────────────────────────────────┐
         │ Invoice No.     H101494                       │
Y=100.2  │ ↑               ↑                             │
         │ Same line (within 3px tolerance)              │
         └──────────────────────────────────────────────┘

Y=120.0  ┌──────────────────────────────────────────────┐
         │ Invoice Date    19-04-2025                    │
         │ Different line (>3px from Y=100)              │
         └──────────────────────────────────────────────┘
```

### 5.3 Pattern-Based Field Extraction

#### Invoice Number Extraction

```python
def _extract_invoice_number(self, text: str) -> Optional[str]:
    patterns = [
        r'Tax\s+Invoice\s*#[:\s]*([A-Z0-9-]+)',    # Tax Invoice #: INV-123
        r'Invoice\s+No\.?\s*[:\s]*([A-Z0-9-]+)',   # Invoice No. H101494
        r'Invoice\s*#[:\s]*([A-Z0-9-]+)',          # Invoice #: XXX
        r'Receipt\s+No\.?\s*[:\s]*([A-Z0-9-]+)',   # Receipt No. XXX
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None  # Flag as warning
```

#### Multi-Format Date Parsing

```python
DATE_PATTERNS = [
    (r'(\d{1,2}\s+\w{3}\s+\d{4})', '%d %b %Y'),   # 10 Jan 2026
    (r'(\d{2}-\d{2}-\d{4})', '%d-%m-%Y'),          # 19-04-2025
    (r'(\d{2}/\d{2}/\d{4})', '%d/%m/%Y'),          # 10/01/2026
    (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),          # 2026-01-10
]

# All dates normalized to YYYY-MM-DD output format
```

#### Amount Extraction

```python
def _extract_amounts(self, text: str) -> Dict:
    amounts = {"subtotal": None, "gst": None, "total": None}

    # GST patterns (handles various formats)
    gst_patterns = [
        r'GST\s*\([^)]*\)[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',
        r'Inclusive\s+of\s+GST[^:]*[:\s]*\$?\s*([\d,]+\.\d{2})',
    ]

    # Total patterns (careful not to match SUBTOTAL)
    total_patterns = [
        r'(?<!SUB)TOTAL[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',
        r'Amount\s+Paid[:\s]*\$?\s*([\d,]+\.\d{2})',
    ]

    # ... extraction logic

    # Auto-calculate subtotal if missing
    if amounts["subtotal"] is None and amounts["total"] and amounts["gst"]:
        amounts["subtotal"] = round(amounts["total"] - amounts["gst"], 2)

    return amounts
```

### 5.4 Handling Different Invoice Formats

The parser handles multiple invoice layouts through flexible pattern matching:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INVOICE FORMAT VARIATIONS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FORMAT A (City Osteopathy)          FORMAT B (OneDoctors)              │
│  ─────────────────────────           ─────────────────────              │
│                                                                         │
│  Tax Invoice #: INV-2601000859       Invoice No. H101494                │
│  Issued on: 10 Jan 2026              Invoice Date : 19-04-2025          │
│                                                                         │
│  Patient:                            MARK TAN JEN WEI                   │
│  Mark Tan Jen Wei (XXXXX238J)        Ref ID: H726872                    │
│                                                                         │
│  SUBTOTAL: SGD 170.00                Inclusive of GST 9%: $3.78         │
│  GST (9%): SGD 15.30                 Total: $45.78                      │
│  TOTAL: SGD 185.30                                                      │
│                                                                         │
│  [No diagnosis]                      Diagnosis: Acute upper             │
│                                      respiratory infection              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Inference Layer

The inference layer (added in v2.0) provides automatic field resolution using a **layered approach**:

1. **Rule-based keyword matching** - Fast, deterministic, zero API cost
2. **SLM fallback (GPT-4o-mini)** - Only called when keywords don't match
3. **HITL flagging** - Fields that cannot be resolved are flagged for human review

### 6.1 Design Rationale

The inference layer addresses a key architectural question: **Where should field inference happen?**

**Original Design:** Upstream agent performs all inference
- Parser returns raw data + flags
- Agent uses template keywords to infer values
- Agent handles all HITL interactions

**New Design (v2.0):** Parser service performs inference internally
- Parser returns **complete, ready-to-use** data where possible
- Only genuinely unresolvable fields flagged for HITL
- Method transparency shows **how** each value was inferred

**Benefits:**
- Single responsibility: Service returns an answered template
- Consistency: All consumers get the same inference quality
- Reduced latency: One call instead of parse → template fetch → inference
- Simpler integration: Upstream agents receive pre-resolved fields

### 6.2 Inference Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INFERENCE PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

POST /parse?inference=true
         │
         ▼
┌─────────────────────┐
│ Deterministic Parser │  PyMuPDF extraction (unchanged)
│                     │  Returns: extracted data + diagnosisRaw, providerName
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  KeywordMatcher     │  Rule-based matching against template keywords
│                     │  Fast, deterministic, zero cost
└──────────┬──────────┘
           │
     Match found? ──Yes──▶ Return with method="keyword_match"
           │
           No
           │
           ▼
┌─────────────────────┐
│  SLMClient          │  OpenAI GPT-4o-mini (only if enabled)
│  (GPT-4o-mini)      │  Structured output via instructor library
└──────────┬──────────┘
           │
  confidence >= 0.8? ──Yes──▶ Return with method="slm"
           │
           No
           │
           ▼
   Return with method="hitl_required"
   (Added to hitl_required list)
```

### 6.3 Module Structure

| File | Purpose |
|------|---------|
| `src/inference/__init__.py` | Module exports |
| `src/inference/config.py` | `InferenceSettings` - env var configuration |
| `src/inference/models.py` | Pydantic models for inference results |
| `src/inference/keyword_matcher.py` | Rule-based keyword matching engine |
| `src/inference/slm_client.py` | OpenAI GPT-4o-mini client with instructor |
| `src/inference/inference_service.py` | Orchestrator service |

### 6.4 Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required for SLM fallback (optional - keyword matching works without this)
INFERENCE_OPENAI_API_KEY=sk-proj-xxxxx

# Model settings
INFERENCE_OPENAI_MODEL=gpt-4o-mini
INFERENCE_OPENAI_TIMEOUT=30.0
INFERENCE_OPENAI_MAX_RETRIES=2

# Behavior settings
INFERENCE_ENABLE_SLM_FALLBACK=true
INFERENCE_SLM_CONFIDENCE_THRESHOLD=0.8
```

**Without an API key**, the service runs in **keyword-only mode** - fast and free.

### 6.5 Inference Models

```python
class InferenceMethod(str, Enum):
    """How the inference was performed"""
    KEYWORD_MATCH = "keyword_match"    # Matched template keywords
    SLM = "slm"                        # GPT-4o-mini inference
    HITL_REQUIRED = "hitl_required"    # Needs human review
    NOT_ATTEMPTED = "not_attempted"    # Input was null/empty

class DiagnosisInference(BaseModel):
    code: Optional[str]           # e.g., "C32", "F45"
    description: Optional[str]    # e.g., "Flu/Influenza"
    method: InferenceMethod       # How it was inferred
    confidence: float             # 0.0-1.0
    matched_keywords: List[str]   # Keywords that matched (if method=keyword_match)
    raw_text: Optional[str]       # Original diagnosisRaw
    slm_reasoning: Optional[str]  # SLM explanation (if method=slm)

class BenefitInference(BaseModel):
    category: Optional[str]       # e.g., "outpatient"
    category_description: Optional[str]
    type_code: Optional[str]      # e.g., "OC", "TCM"
    type_description: Optional[str]
    method: InferenceMethod
    confidence: float
    matched_keywords: List[str]
    provider_name: Optional[str]  # Original providerName
    slm_reasoning: Optional[str]

class InferenceResult(BaseModel):
    diagnosis: DiagnosisInference
    benefit: BenefitInference
    hitl_required: List[str]      # Fields needing human review
    inference_attempted: bool
    inference_error: Optional[str]
```

### 6.6 Response Format with Inference

**Request:** `POST /parse?inference=true`

**Response:**
```json
{
  "extracted": {
    "invoiceNumber": "H101494",
    "visitDate": "2025-04-19",
    "providerName": "ONEDOCTORS FAMILY CLINIC",
    "patientName": "MARK TAN JEN WEI",
    "lineItems": [...],
    "subtotal": 42.0,
    "gstAmount": 3.78,
    "paymentAmount": 45.78,
    "currency": "SGD",
    "diagnosisRaw": "Acute upper respiratory infection"
  },
  "inferred": {
    "diagnosis": {
      "code": "C32",
      "description": "Flu/Influenza",
      "method": "keyword_match",
      "confidence": 0.9,
      "matched_keywords": ["respiratory", "infection", "upper respiratory"],
      "raw_text": "Acute upper respiratory infection",
      "slm_reasoning": null
    },
    "benefit": {
      "category": "outpatient",
      "category_description": "Outpatient Medical Claims",
      "type_code": "OC",
      "type_description": "Outpatient Claim (General Practitioner or Specialist visit)",
      "method": "keyword_match",
      "confidence": 0.95,
      "matched_keywords": ["clinic", "doctor", "family clinic"],
      "provider_name": "ONEDOCTORS FAMILY CLINIC",
      "slm_reasoning": null
    },
    "hitl_required": [],
    "inference_attempted": true,
    "inference_error": null
  },
  "inference_required": [],
  "metadata": {
    "success": true,
    "confidence": 1.0,
    "warnings": [],
    "source_file": "invoice2.pdf",
    "abort_reason": null
  }
}
```

### 6.7 Keyword Matching Logic

The `KeywordMatcher` loads keyword mappings from `claimSubmitTemplate2.json`:

```python
# Diagnosis matching example
diagnosis_raw = "Acute upper respiratory infection"
# Template keywords for C32: ["flu", "respiratory", "infection", ...]
# Matches: "respiratory", "infection" → score=2 → confidence=0.8

# Benefit matching example
provider_name = "City Osteopathy & Physiotherapy"
# Template keywords for OC: ["physiotherapy", "osteopathy", "clinic", ...]
# Matches: "osteopathy", "physiotherapy" → score=2 → confidence=0.8
```

**Confidence scoring:** Base 0.6 + 0.1 per keyword match, max 0.95

### 6.8 SLM Fallback

When keyword matching fails and SLM is enabled:

```python
# SLM is called with structured output using instructor
response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=SLMDiagnosisResponse,  # Pydantic model
    messages=[
        {"role": "system", "content": "Map diagnosis text to code..."},
        {"role": "user", "content": f"Raw text: '{diagnosis_raw}'..."}
    ]
)

# Response is automatically validated and typed
if response.confidence >= 0.8:
    return DiagnosisInference(
        code=response.code,
        method=InferenceMethod.SLM,
        slm_reasoning=response.reasoning,
        ...
    )
```

### 6.9 Using the Inference Layer

**With inference (recommended for most use cases):**
```bash
curl -X POST "http://localhost:8000/parse?inference=true" -F "file=@invoice.pdf"
```

**Without inference (backward compatible):**
```bash
curl -X POST "http://localhost:8000/parse" -F "file=@invoice.pdf"
```

**Python usage:**
```python
from src.inference import InferenceService, InferenceSettings

# Keyword-only mode (no API key needed)
service = InferenceService()

# With SLM fallback
settings = InferenceSettings()  # Loads from .env
service = InferenceService(settings)

# Run inference on parsed data
parsed_data = parser.parse(pdf_path).to_json()
result = service.infer(parsed_data)

print(f"Diagnosis: {result.diagnosis.code} via {result.diagnosis.method}")
print(f"Benefit: {result.benefit.type_code} via {result.benefit.method}")
print(f"HITL needed: {result.hitl_required}")
```

---

## 7. API Service

### 7.1 Endpoint Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Test GUI interface |
| `GET` | `/health` | Service health check |
| `GET` | `/docs` | Swagger UI documentation |
| `GET` | `/redoc` | ReDoc documentation |
| `GET` | `/template` | Get claim template (default: v2) |
| `GET` | `/template?version=v1` | Get specific template version |
| `GET` | `/template/list` | List available templates |
| `POST` | `/parse` | Parse invoice (file upload) |
| `POST` | `/parse?inference=true` | Parse invoice with inference layer |
| `POST` | `/parse/base64` | Parse invoice (base64 string) |
| `POST` | `/parse/base64?inference=true` | Parse base64 with inference layer |

### 7.2 Request/Response Formats

#### POST /parse (File Upload)

**Request:**
```http
POST /parse HTTP/1.1
Content-Type: multipart/form-data

------boundary
Content-Disposition: form-data; name="file"; filename="invoice.pdf"
Content-Type: application/pdf

<binary PDF content>
------boundary--
```

**Response:**
```json
{
  "extracted": {
    "invoiceNumber": "H101494",
    "visitDate": "2025-04-19",
    "providerName": "ONEDOCTORS FAMILY CLINIC",
    "patientName": "MARK TAN JEN WEI",
    "lineItems": [
      {"description": "Full Consult", "amount": 0.0},
      {"description": "BEACODYL LINCTUS", "amount": 9.81}
    ],
    "subtotal": 42.0,
    "gstAmount": 3.78,
    "paymentAmount": 45.78,
    "currency": "SGD",
    "diagnosisRaw": "Acute upper respiratory infection"
  },
  "inference_required": [
    "diagnosisCode: raw text found, needs mapping",
    "benefitType: requires inference from provider name",
    "benefitCategory: requires inference"
  ],
  "metadata": {
    "success": true,
    "confidence": 1.0,
    "warnings": [],
    "source_file": "invoice2.pdf",
    "abort_reason": null
  }
}
```

#### POST /parse/base64

**Request:**
```json
{
  "file_content": "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PC...",
  "filename": "invoice.pdf"
}
```

**Response:** Same format as `/parse`

### 7.3 Error Responses

| Status | Condition | Response |
|--------|-----------|----------|
| 400 | Invalid file type | `{"detail": "Only PDF files are supported"}` |
| 400 | Invalid base64 | `{"detail": "Invalid base64 encoding"}` |
| 400 | Not a PDF | `{"detail": "Content does not appear to be a valid PDF"}` |
| 500 | Parse error | `{"detail": "Failed to parse invoice: <error>"}` |

---

## 8. Data Flow

### 8.1 Complete Request Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE DATA FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

     ┌─────────────┐
     │   Client    │
     │  (Agent)    │
     └──────┬──────┘
            │
            │ 1. POST /parse with PDF
            ▼
     ┌─────────────────────────────────────────────────────────────────┐
     │                      FastAPI Endpoint                           │
     │                                                                 │
     │  • Validate file type (.pdf)                                   │
     │  • Save to temp file                                           │
     │  • Call parser                                                 │
     └──────────────────────────────┬──────────────────────────────────┘
                                    │
                                    │ 2. Parse PDF
                                    ▼
     ┌─────────────────────────────────────────────────────────────────┐
     │                   MedicalInvoiceParser                          │
     │                                                                 │
     │  ┌─────────────────┐                                           │
     │  │ _validate_doc() │ Check text layer integrity                │
     │  └────────┬────────┘                                           │
     │           │                                                     │
     │           ▼                                                     │
     │  ┌─────────────────┐                                           │
     │  │ get_text("words")│ PyMuPDF word extraction                  │
     │  └────────┬────────┘                                           │
     │           │                                                     │
     │           ▼                                                     │
     │  ┌─────────────────┐                                           │
     │  │ _group_into_    │ Y-coordinate line grouping                │
     │  │ lines()         │                                           │
     │  └────────┬────────┘                                           │
     │           │                                                     │
     │           ▼                                                     │
     │  ┌─────────────────┐                                           │
     │  │ _extract_*()    │ Pattern-based field extraction            │
     │  │ methods         │ (invoice#, date, amounts, etc.)           │
     │  └────────┬────────┘                                           │
     │           │                                                     │
     │           ▼                                                     │
     │  ┌─────────────────┐                                           │
     │  │ _flag_inference │ Mark fields needing inference             │
     │  │ _fields()       │                                           │
     │  └────────┬────────┘                                           │
     │           │                                                     │
     └───────────┼─────────────────────────────────────────────────────┘
                 │
                 │ 3. Return MedicalInvoiceResult
                 ▼
     ┌─────────────────────────────────────────────────────────────────┐
     │                    Result Formatting                            │
     │                                                                 │
     │  result.to_json(source_file="invoice.pdf")                     │
     │                                                                 │
     │  {                                                              │
     │    "extracted": { ... },                                       │
     │    "inference_required": [ ... ],                              │
     │    "metadata": { ... }                                         │
     │  }                                                              │
     └──────────────────────────────┬──────────────────────────────────┘
                                    │
                                    │ 4. JSON Response
                                    ▼
     ┌─────────────┐
     │   Client    │
     │  (Agent)    │
     └─────────────┘
```

### 8.2 Field Extraction Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FIELD EXTRACTION PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────┘

  PDF Document
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        RAW TEXT EXTRACTION                          │
  │                                                                     │
  │  page.get_text()  ──────────────────────▶  Full text string        │
  │  page.get_text("words")  ───────────────▶  Positioned words        │
  └─────────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                      STRUCTURED EXTRACTION                          │
  │                                                                     │
  │  Full Text                    Positioned Words                      │
  │      │                              │                               │
  │      ▼                              ▼                               │
  │  ┌──────────────┐            ┌──────────────┐                      │
  │  │ Invoice #    │            │ Provider     │                      │
  │  │ Visit Date   │            │ Name         │                      │
  │  │ Diagnosis    │            │ (from header │                      │
  │  │ Amounts      │            │  lines)      │                      │
  │  └──────────────┘            └──────────────┘                      │
  │         │                           │                               │
  │         └───────────┬───────────────┘                               │
  │                     ▼                                               │
  │              ┌──────────────┐                                       │
  │              │  Line Items  │                                       │
  │              │ (from table  │                                       │
  │              │  region)     │                                       │
  │              └──────────────┘                                       │
  └─────────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        OUTPUT ASSEMBLY                              │
  │                                                                     │
  │  {                                                                  │
  │    "invoiceNumber": "H101494",           ◄── from regex            │
  │    "visitDate": "2025-04-19",            ◄── from regex + parse    │
  │    "providerName": "ONEDOCTORS...",      ◄── from header lines     │
  │    "patientName": "MARK TAN...",         ◄── from regex/lines      │
  │    "lineItems": [...],                   ◄── from table region     │
  │    "subtotal": 42.0,                     ◄── from regex            │
  │    "gstAmount": 3.78,                    ◄── from regex            │
  │    "paymentAmount": 45.78,               ◄── from regex            │
  │    "currency": "SGD",                    ◄── from prefix           │
  │    "diagnosisRaw": "Acute upper..."      ◄── from regex            │
  │  }                                                                  │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Template System

### 9.1 Template Purpose

Templates serve two purposes:
1. **Schema Definition:** Defines expected output structure for claim submission
2. **Inference Mapping:** Provides keyword hints for field inference

### 9.2 Template Versions

| Version | File | Features |
|---------|------|----------|
| v1 | `claimSubmitTemplate.json` | Basic schema, no keyword mappings |
| v2 | `claimSubmitTemplate2.json` | Enhanced with keyword mappings |

### 9.3 Template Structure (v2)

```json
{
  "claimant": {
    "fullName": null,           // From HR lookup
    "employeeId": null,         // From HR lookup
    "department": null,         // From HR lookup
    "contactInfo": { ... }
  },

  "claimDetails": {
    "invoiceNumber": null,      // Extracted
    "visitDate": null,          // Extracted
    "benefitCategory": null,    // Inferred
    "benefitType": null,        // Inferred
    "providerName": null,       // Extracted
    "diagnosisRaw": null,       // Extracted (pass-through)
    "diagnosisList": [...],     // Inferred from diagnosisRaw
    "subtotal": null,           // Extracted
    "gstAmount": null,          // Extracted
    "paymentAmount": null,      // Extracted
    "currency": "SGD"
  },

  "_meta": {
    "version": "2.0",
    "usage": {
      "diagnosisRaw": "Use _enums.diagnosisCode.keywords to map",
      "benefitType": "Infer from providerName using keywords"
    }
  },

  "_enums": {
    "benefitCategory": { ... },
    "diagnosisCode": [
      {
        "code": "F45",
        "description": "Fracture/Sprain/Pain/Injury",
        "keywords": ["fracture", "sprain", "pain", "physiotherapy"]
      },
      {
        "code": "C32",
        "description": "Flu/Influenza",
        "keywords": ["flu", "respiratory", "cold", "fever", "cough"]
      }
    ]
  }
}
```

### 9.4 Keyword Mapping Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     KEYWORD MAPPING PROCESS                              │
└─────────────────────────────────────────────────────────────────────────┘

  Parser Output:
  ─────────────
  diagnosisRaw: "Acute upper respiratory infection"
  providerName: "City Osteopathy & Physiotherapy"

       │
       ▼

  Template Lookup:
  ────────────────

  diagnosisCode keywords:
  ┌──────────────────────────────────────────────────────────────────┐
  │  F45: ["fracture", "sprain", "pain", "physiotherapy", ...]      │
  │  C32: ["flu", "respiratory", "cold", "fever", "infection", ...] │
  └──────────────────────────────────────────────────────────────────┘

  "respiratory" + "infection" matches C32 keywords

       │
       ▼

  benefitType keywords:
  ┌──────────────────────────────────────────────────────────────────┐
  │  OC: ["clinic", "physiotherapy", "osteopathy", "specialist"]    │
  │  TCM: ["tcm", "acupuncture", "chinese medicine"]                │
  └──────────────────────────────────────────────────────────────────┘

  "Osteopathy" + "Physiotherapy" matches OC keywords

       │
       ▼

  Inferred Values:
  ────────────────
  diagnosisCode: "C32"
  benefitType: "OC"
  benefitCategory: "outpatient"
```

---

## 10. Integration Guide for Parent Agents

### 10.1 Integration Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT INTEGRATION PATTERN                             │
└─────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │                        PARENT AGENT                                  │
  │                                                                     │
  │  1. User uploads invoice                                            │
  │       │                                                             │
  │       ▼                                                             │
  │  2. Agent calls POST /parse                                         │
  │       │                                                             │
  │       ▼                                                             │
  │  3. Agent receives extracted data + inference_required              │
  │       │                                                             │
  │       ▼                                                             │
  │  4. Agent calls GET /template to get keyword mappings               │
  │       │                                                             │
  │       ▼                                                             │
  │  5. Agent performs inference:                                       │
  │       • diagnosisRaw → diagnosisCode (using keywords)              │
  │       • providerName → benefitType (using keywords)                │
  │       • patientName → employeeId (HR lookup)                       │
  │       │                                                             │
  │       ▼                                                             │
  │  6. Agent asks user to confirm/correct inferred values              │
  │       │                                                             │
  │       ▼                                                             │
  │  7. Agent submits complete claim to claims API                      │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Tool Definition for LLM Agents

If your agent framework uses tool/function calling:

```json
{
  "name": "parse_medical_invoice",
  "description": "Extract structured data from a medical invoice PDF. Returns extracted fields and flags fields requiring inference (benefitType, diagnosisCode).",
  "parameters": {
    "type": "object",
    "properties": {
      "file_content": {
        "type": "string",
        "description": "Base64-encoded PDF file content"
      },
      "filename": {
        "type": "string",
        "description": "Original filename (optional)"
      }
    },
    "required": ["file_content"]
  }
}
```

```json
{
  "name": "get_claim_template",
  "description": "Get the claim submission template with keyword mappings for inference. Use this to map extracted diagnosisRaw to diagnosisCode and providerName to benefitType.",
  "parameters": {
    "type": "object",
    "properties": {
      "version": {
        "type": "string",
        "enum": ["v1", "v2"],
        "default": "v2",
        "description": "Template version. v2 includes keyword mappings."
      }
    }
  }
}
```

### 10.3 Python Integration Example (With Inference)

```python
import httpx
import base64
from pathlib import Path

PARSER_URL = "http://localhost:8000"

class MedicalClaimAgent:
    """Example agent that uses the medical invoice parser"""

    def __init__(self):
        self.client = httpx.Client(base_url=PARSER_URL)
        self.template = None

    def load_template(self):
        """Load template with keyword mappings"""
        response = self.client.get("/template?version=v2")
        self.template = response.json()

    def parse_invoice(self, pdf_path: str) -> dict:
        """Parse a medical invoice PDF"""
        with open(pdf_path, "rb") as f:
            files = {"file": (Path(pdf_path).name, f, "application/pdf")}
            response = self.client.post("/parse", files=files)
        return response.json()

    def parse_invoice_base64(self, content: bytes, filename: str) -> dict:
        """Parse invoice from base64 content"""
        payload = {
            "file_content": base64.b64encode(content).decode(),
            "filename": filename
        }
        response = self.client.post("/parse/base64", json=payload)
        return response.json()

    def infer_diagnosis_code(self, diagnosis_raw: str) -> str:
        """Map raw diagnosis text to code using keywords"""
        if not diagnosis_raw:
            return None

        diagnosis_lower = diagnosis_raw.lower()

        for diagnosis in self.template["_enums"]["diagnosisCode"]:
            for keyword in diagnosis["keywords"]:
                if keyword in diagnosis_lower:
                    return diagnosis["code"]

        return None  # No match - needs human review

    def infer_benefit_type(self, provider_name: str) -> tuple:
        """Map provider name to benefit category and type"""
        if not provider_name:
            return None, None

        provider_lower = provider_name.lower()

        for category, config in self.template["_enums"]["benefitCategory"].items():
            for benefit_type in config["benefitTypes"]:
                for keyword in benefit_type["keywords"]:
                    if keyword in provider_lower:
                        return category, benefit_type["code"]

        return None, None

    def process_claim(self, pdf_path: str) -> dict:
        """Complete claim processing workflow"""
        # Ensure template is loaded
        if not self.template:
            self.load_template()

        # Step 1: Parse invoice
        result = self.parse_invoice(pdf_path)

        if not result["metadata"]["success"]:
            raise Exception(f"Parse failed: {result['metadata']['abort_reason']}")

        extracted = result["extracted"]

        # Step 2: Perform inference
        diagnosis_code = self.infer_diagnosis_code(extracted.get("diagnosisRaw"))
        category, benefit_type = self.infer_benefit_type(extracted.get("providerName"))

        # Step 3: Build claim payload
        claim = {
            "claimDetails": {
                "invoiceNumber": extracted["invoiceNumber"],
                "visitDate": extracted["visitDate"],
                "providerName": extracted["providerName"],
                "benefitCategory": category,
                "benefitType": benefit_type,
                "diagnosisList": [{
                    "diagnosisCode": diagnosis_code,
                    "diagnosisDescription": extracted.get("diagnosisRaw")
                }] if diagnosis_code else [],
                "subtotal": extracted["subtotal"],
                "gstAmount": extracted["gstAmount"],
                "paymentAmount": extracted["paymentAmount"],
                "currency": extracted["currency"]
            },
            "metadata": {
                "parser_confidence": result["metadata"]["confidence"],
                "inference_performed": True,
                "needs_review": diagnosis_code is None or benefit_type is None
            }
        }

        return claim


# Usage example
if __name__ == "__main__":
    agent = MedicalClaimAgent()

    claim = agent.process_claim("resources/statements/medical_invoice_statements/invoice2.pdf")

    print("Processed Claim:")
    print(f"  Invoice: {claim['claimDetails']['invoiceNumber']}")
    print(f"  Total: {claim['claimDetails']['currency']} {claim['claimDetails']['paymentAmount']}")
    print(f"  Benefit Type: {claim['claimDetails']['benefitType']}")
    print(f"  Diagnosis: {claim['claimDetails']['diagnosisList']}")
    print(f"  Needs Review: {claim['metadata']['needs_review']}")
```

### 10.4 JavaScript/TypeScript Integration

```typescript
interface ParseResponse {
  extracted: {
    invoiceNumber: string | null;
    visitDate: string | null;
    providerName: string | null;
    patientName: string | null;
    lineItems: Array<{ description: string; amount: number }>;
    subtotal: number | null;
    gstAmount: number | null;
    paymentAmount: number | null;
    currency: string;
    diagnosisRaw: string | null;
  };
  inference_required: string[];
  metadata: {
    success: boolean;
    confidence: number;
    warnings: string[];
    source_file: string | null;
    abort_reason: string | null;
  };
}

class MedicalInvoiceClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async parseInvoice(file: File): Promise<ParseResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/parse`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Parse failed: ${response.statusText}`);
    }

    return response.json();
  }

  async parseInvoiceBase64(content: string, filename: string): Promise<ParseResponse> {
    const response = await fetch(`${this.baseUrl}/parse/base64`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_content: content, filename }),
    });

    if (!response.ok) {
      throw new Error(`Parse failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getTemplate(version: string = 'v2'): Promise<any> {
    const response = await fetch(`${this.baseUrl}/template?version=${version}`);
    return response.json();
  }
}

// Usage
const client = new MedicalInvoiceClient();

// With file input
const fileInput = document.querySelector('input[type="file"]');
fileInput.addEventListener('change', async (e) => {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) {
    const result = await client.parseInvoice(file);
    console.log('Extracted:', result.extracted);
    console.log('Needs inference:', result.inference_required);
  }
});
```

### 10.5 cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Get template with keyword mappings
curl http://localhost:8000/template?version=v2

# Parse invoice WITHOUT inference (backward compatible)
curl -X POST http://localhost:8000/parse \
  -F "file=@invoice.pdf"

# Parse invoice WITH inference (recommended)
curl -X POST "http://localhost:8000/parse?inference=true" \
  -F "file=@invoice.pdf"

# Parse invoice (base64) with inference
curl -X POST "http://localhost:8000/parse/base64?inference=true" \
  -H "Content-Type: application/json" \
  -d '{
    "file_content": "'$(base64 -i invoice.pdf)'",
    "filename": "invoice.pdf"
  }'
```

---

## 11. Error Handling & Edge Cases

### 11.1 Confidence Scoring

The parser maintains a confidence score that degrades when issues are encountered:

| Condition | Confidence Impact |
|-----------|-------------------|
| Clean extraction | 1.0 (100%) |
| Insufficient text content | × 0.5 |
| Expected headers not found | × 0.7 |
| Diagnosis not found | × 0.9 |
| Field extraction failed | Warning added |

### 11.2 Common Edge Cases

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EDGE CASE HANDLING                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CASE: Scanned PDF (no text layer)                                     │
│  ────────────────────────────────────                                  │
│  Detection: len(text.strip()) < 50                                     │
│  Response:  confidence × 0.5, warning added                            │
│  Action:    Upstream should route to OCR/vision pipeline               │
│                                                                         │
│  CASE: Missing invoice number                                          │
│  ───────────────────────────────                                       │
│  Detection: All regex patterns fail                                    │
│  Response:  Warning added, field = null                                │
│  Action:    Upstream should flag for manual entry                      │
│                                                                         │
│  CASE: Ambiguous date format                                           │
│  ──────────────────────────────                                        │
│  Detection: Multiple date patterns match                               │
│  Response:  First valid parse used                                     │
│  Action:    All dates normalized to YYYY-MM-DD                         │
│                                                                         │
│  CASE: No diagnosis on invoice                                         │
│  ───────────────────────────────                                       │
│  Detection: Diagnosis regex returns null                               │
│  Response:  diagnosisRaw = null, confidence × 0.9                      │
│  Action:    Flagged in inference_required for manual selection         │
│                                                                         │
│  CASE: GST not itemized                                                │
│  ──────────────────────────                                            │
│  Detection: Only total found, no GST line                              │
│  Response:  gstAmount = null (cannot calculate)                        │
│  Action:    Warning added, may need manual entry                       │
│                                                                         │
│  CASE: Subtotal missing but total + GST present                        │
│  ───────────────────────────────────────────────                       │
│  Detection: subtotal pattern fails                                     │
│  Response:  Auto-calculate: subtotal = total - gstAmount               │
│  Action:    Warning added about calculated value                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Error Response Handling

```python
# Agent-side error handling example
def handle_parse_result(result: dict) -> dict:
    """Handle parser response with appropriate fallbacks"""

    metadata = result["metadata"]

    # Check for parse failure
    if not metadata["success"]:
        return {
            "status": "failed",
            "reason": metadata["abort_reason"],
            "action": "route_to_manual_processing"
        }

    # Check confidence threshold
    if metadata["confidence"] < 0.7:
        return {
            "status": "low_confidence",
            "confidence": metadata["confidence"],
            "warnings": metadata["warnings"],
            "action": "flag_for_human_review",
            "data": result["extracted"]
        }

    # Check for critical missing fields
    extracted = result["extracted"]
    critical_fields = ["invoiceNumber", "paymentAmount", "providerName"]

    missing = [f for f in critical_fields if not extracted.get(f)]
    if missing:
        return {
            "status": "incomplete",
            "missing_fields": missing,
            "action": "request_manual_entry",
            "data": extracted
        }

    # Success
    return {
        "status": "success",
        "data": extracted,
        "inference_required": result["inference_required"]
    }
```

---

## 12. Testing & Validation

### 12.1 Running the Test Suite

```bash
# Run parser directly
uv run python src/parsers/medical_invoice_parser.py

# Run API test script
uv run python scripts/test_api.py

# Run Jupyter notebook tests
uv run jupyter notebook notebooks/test_medical_invoice_parser.ipynb
```

### 12.2 Test GUI

Access the test GUI at `http://localhost:8000` when the server is running:

```bash
# Start server
uv run uvicorn src.api.medical_invoice_api:app --reload

# Open browser to http://localhost:8000
```

### 12.3 Validation Checklist

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VALIDATION CHECKLIST                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  EXTRACTION ACCURACY                                                    │
│  □ Invoice number matches PDF                                          │
│  □ Visit date correctly parsed and normalized                          │
│  □ Provider name extracted from header                                 │
│  □ Patient name identified                                             │
│  □ Amounts match (subtotal + GST = total)                             │
│  □ Line items captured with descriptions                               │
│  □ Diagnosis raw text extracted (when present)                         │
│                                                                         │
│  INFERENCE FLAGS                                                        │
│  □ diagnosisCode flagged when raw text present                        │
│  □ diagnosisCode flagged when raw text missing                        │
│  □ benefitType flagged for inference                                  │
│  □ benefitCategory flagged for inference                              │
│                                                                         │
│  METADATA                                                               │
│  □ success=true on valid PDFs                                         │
│  □ confidence reflects extraction quality                             │
│  □ warnings populated for issues                                      │
│  □ source_file included in response                                   │
│                                                                         │
│  API ENDPOINTS                                                          │
│  □ /health returns 200                                                │
│  □ /parse accepts file upload                                         │
│  □ /parse/base64 accepts base64 string                               │
│  □ /template returns schema with keywords                             │
│  □ CORS headers present                                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Deployment

### 13.1 Local Development

```bash
# Install dependencies
uv sync --group api --group dev

# Run with hot reload
uv run uvicorn src.api.medical_invoice_api:app --reload --host 0.0.0.0 --port 8000
```

### 13.2 Production Deployment

```bash
# Install production dependencies only
uv sync --group api

# Run with production settings
uv run uvicorn src.api.medical_invoice_api:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log
```

### 13.3 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY resources/jsonTemplates/ ./resources/jsonTemplates/

# Install dependencies
RUN uv sync --group api --no-dev

# Run server
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.api.medical_invoice_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t medical-invoice-parser .
docker run -p 8000:8000 medical-invoice-parser
```

### 13.4 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEFAULT_TEMPLATE` | `v2` | Default template version |
| `LOG_LEVEL` | `info` | Logging verbosity |
| `INFERENCE_OPENAI_API_KEY` | *(none)* | OpenAI API key for SLM fallback |
| `INFERENCE_OPENAI_MODEL` | `gpt-4o-mini` | Model for inference |
| `INFERENCE_ENABLE_SLM_FALLBACK` | `true` | Enable SLM when keywords fail |
| `INFERENCE_SLM_CONFIDENCE_THRESHOLD` | `0.8` | Min confidence for SLM results |

### 13.5 Azure Deployment

This section covers deploying the Medical Invoice Parser as a microservice on Microsoft Azure.

#### Deployment Options Comparison

| Option | Best For | Pros | Cons |
|--------|----------|------|------|
| **Azure Container Apps** | Production microservices | Auto-scaling, managed, cost-effective | Limited customization |
| **Azure App Service** | Simple web apps | Easy deployment, built-in CI/CD | Less control over infrastructure |
| **Azure Kubernetes Service (AKS)** | Complex multi-service architectures | Full control, enterprise-grade | Higher complexity & cost |
| **Azure Container Instances (ACI)** | Dev/test, batch jobs | Simple, pay-per-second | No auto-scaling |

**Recommended:** Azure Container Apps for production microservices.

---

#### Option A: Azure Container Apps (Recommended)

**Prerequisites:**
- Azure CLI installed (`az --version`)
- Docker installed
- Azure subscription with Container Apps enabled

**Step 1: Prepare Production Dockerfile**

Create `Dockerfile.azure` in project root:

```dockerfile
# Dockerfile.azure - Production-optimized for Azure
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --group api --group llm --no-dev --frozen

# Copy application code
COPY src/ ./src/
COPY resources/jsonTemplates/ ./resources/jsonTemplates/
COPY gui/ ./gui/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with production settings
CMD ["uv", "run", "uvicorn", "src.api.medical_invoice_api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
```

**Step 2: Set Up Azure Resources**

```bash
# Login to Azure
az login

# Set variables (customize these)
RESOURCE_GROUP="rg-medical-parser"
LOCATION="southeastasia"  # Choose your region
ACR_NAME="acrmedicalparser"  # Must be globally unique
APP_NAME="medical-invoice-parser"
ENVIRONMENT_NAME="env-medical-parser"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
```

**Step 3: Build and Push Docker Image**

```bash
# Build image
docker build -t $ACR_LOGIN_SERVER/medical-invoice-parser:latest -f Dockerfile.azure .

# Login to ACR
docker login $ACR_LOGIN_SERVER -u $ACR_USERNAME -p $ACR_PASSWORD

# Push image
docker push $ACR_LOGIN_SERVER/medical-invoice-parser:latest
```

**Step 4: Create Container Apps Environment**

```bash
# Install Container Apps extension
az extension add --name containerapp --upgrade

# Create Container Apps environment
az containerapp env create \
    --name $ENVIRONMENT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION
```

**Step 5: Deploy Container App**

```bash
# Deploy the container app
az containerapp create \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENVIRONMENT_NAME \
    --image $ACR_LOGIN_SERVER/medical-invoice-parser:latest \
    --registry-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 5 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --env-vars \
        "LOG_LEVEL=info" \
        "DEFAULT_TEMPLATE=v2" \
        "INFERENCE_ENABLE_SLM_FALLBACK=true"

# Get the app URL
az containerapp show \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress.fqdn" -o tsv
```

**Step 6: Configure Secrets (for OpenAI API Key)**

```bash
# Add OpenAI API key as a secret
az containerapp secret set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --secrets "openai-api-key=your-openai-api-key-here"

# Update app to use the secret as environment variable
az containerapp update \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars "INFERENCE_OPENAI_API_KEY=secretref:openai-api-key"
```

**Step 7: Configure Auto-Scaling Rules**

```bash
# Scale based on HTTP requests
az containerapp update \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --min-replicas 1 \
    --max-replicas 10 \
    --scale-rule-name "http-scaling" \
    --scale-rule-type "http" \
    --scale-rule-http-concurrency 50
```

---

#### Option B: Azure App Service

For simpler deployments without container management.

**Step 1: Create App Service**

```bash
# Set variables
RESOURCE_GROUP="rg-medical-parser"
LOCATION="southeastasia"
APP_SERVICE_PLAN="asp-medical-parser"
WEB_APP_NAME="medical-invoice-parser"  # Must be globally unique

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan (Linux)
az appservice plan create \
    --name $APP_SERVICE_PLAN \
    --resource-group $RESOURCE_GROUP \
    --sku B2 \
    --is-linux

# Create Web App with Python 3.12
az webapp create \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --runtime "PYTHON:3.12"
```

**Step 2: Configure Startup Command**

```bash
# Set startup command
az webapp config set \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --startup-file "pip install uv && uv sync --group api --group llm && uv run uvicorn src.api.medical_invoice_api:app --host 0.0.0.0 --port 8000"
```

**Step 3: Deploy from Git**

```bash
# Configure deployment from local Git
az webapp deployment source config-local-git \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP

# Get deployment URL
DEPLOY_URL=$(az webapp deployment source config-local-git \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query url -o tsv)

# Add Azure as remote and push
git remote add azure $DEPLOY_URL
git push azure main
```

**Step 4: Configure Environment Variables**

```bash
az webapp config appsettings set \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        LOG_LEVEL=info \
        DEFAULT_TEMPLATE=v2 \
        INFERENCE_ENABLE_SLM_FALLBACK=true \
        INFERENCE_OPENAI_API_KEY=@Microsoft.KeyVault(SecretUri=https://your-keyvault.vault.azure.net/secrets/openai-api-key/)
```

---

#### Option C: Azure Kubernetes Service (AKS)

For enterprise deployments with multiple microservices.

**Step 1: Create Kubernetes Manifests**

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: medical-invoice-parser
  labels:
    app: medical-invoice-parser
spec:
  replicas: 3
  selector:
    matchLabels:
      app: medical-invoice-parser
  template:
    metadata:
      labels:
        app: medical-invoice-parser
    spec:
      containers:
      - name: parser
        image: acrmedicalparser.azurecr.io/medical-invoice-parser:latest
        ports:
        - containerPort: 8000
        env:
        - name: LOG_LEVEL
          value: "info"
        - name: INFERENCE_OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secrets
              key: api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: medical-invoice-parser-service
spec:
  selector:
    app: medical-invoice-parser
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: medical-invoice-parser-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: medical-invoice-parser
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Step 2: Deploy to AKS**

```bash
# Create AKS cluster
az aks create \
    --resource-group $RESOURCE_GROUP \
    --name aks-medical-parser \
    --node-count 3 \
    --enable-addons monitoring \
    --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group $RESOURCE_GROUP --name aks-medical-parser

# Create secret for OpenAI API key
kubectl create secret generic openai-secrets \
    --from-literal=api-key=your-openai-api-key

# Apply manifests
kubectl apply -f k8s/deployment.yaml

# Get external IP
kubectl get service medical-invoice-parser-service
```

---

#### CI/CD with GitHub Actions

Create `.github/workflows/azure-deploy.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  AZURE_CONTAINER_REGISTRY: acrmedicalparser
  CONTAINER_APP_NAME: medical-invoice-parser
  RESOURCE_GROUP: rg-medical-parser

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}

    - name: Login to ACR
      run: |
        az acr login --name ${{ env.AZURE_CONTAINER_REGISTRY }}

    - name: Build and push image
      run: |
        docker build -t ${{ env.AZURE_CONTAINER_REGISTRY }}.azurecr.io/medical-invoice-parser:${{ github.sha }} -f Dockerfile.azure .
        docker push ${{ env.AZURE_CONTAINER_REGISTRY }}.azurecr.io/medical-invoice-parser:${{ github.sha }}

    - name: Deploy to Container Apps
      run: |
        az containerapp update \
          --name ${{ env.CONTAINER_APP_NAME }} \
          --resource-group ${{ env.RESOURCE_GROUP }} \
          --image ${{ env.AZURE_CONTAINER_REGISTRY }}.azurecr.io/medical-invoice-parser:${{ github.sha }}
```

---

#### Monitoring and Logging

**Enable Application Insights:**

```bash
# Create Application Insights
az monitor app-insights component create \
    --app ai-medical-parser \
    --location $LOCATION \
    --resource-group $RESOURCE_GROUP

# Get instrumentation key
APPINSIGHTS_KEY=$(az monitor app-insights component show \
    --app ai-medical-parser \
    --resource-group $RESOURCE_GROUP \
    --query instrumentationKey -o tsv)

# Add to Container App
az containerapp update \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars "APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$APPINSIGHTS_KEY"
```

**View Logs:**

```bash
# Stream logs
az containerapp logs show \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --follow

# Query logs (last 1 hour)
az containerapp logs show \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --tail 100
```

---

#### Cost Estimation (Southeast Asia Region)

| Resource | Configuration | Est. Monthly Cost |
|----------|---------------|-------------------|
| Container Apps | 0.5 vCPU, 1GB RAM, 2 replicas avg | ~$30-50 |
| Container Registry | Basic tier | ~$5 |
| Application Insights | 5GB ingestion/month | ~$12 |
| **Total** | | **~$50-70/month** |

*Costs vary based on usage. Use Azure Pricing Calculator for accurate estimates.*

---

#### Security Best Practices

1. **Use Managed Identity** instead of storing credentials:
   ```bash
   az containerapp identity assign \
       --name $APP_NAME \
       --resource-group $RESOURCE_GROUP \
       --system-assigned
   ```

2. **Store secrets in Azure Key Vault:**
   ```bash
   az keyvault create --name kv-medical-parser --resource-group $RESOURCE_GROUP
   az keyvault secret set --vault-name kv-medical-parser --name openai-api-key --value "sk-..."
   ```

3. **Enable HTTPS only** (default in Container Apps)

4. **Configure CORS** for your frontend domains in `medical_invoice_api.py`

5. **Use private endpoints** for production to restrict network access

---

#### Troubleshooting Azure App Service Deployments

This section documents common issues encountered when deploying to Azure App Service with Git-based deployment (Oryx build system) and their solutions.

##### Problem: Container Exits with Code 1, App Returns 503

**Symptoms:**
- App Service returns "503 Service Unavailable" or "Application Error"
- Container logs show `Container has finished running with exit code: 1`
- Site startup probe fails after ~30 seconds

**Root Cause: Module Import Errors**

Azure's Oryx build system extracts the application to a temporary directory (e.g., `/tmp/8de57103d0cfdd4/`) and sets PYTHONPATH to the virtual environment. This can break Python imports that rely on the working directory structure.

**Debugging Steps:**

1. **Download and examine container logs:**
   ```bash
   # Download logs
   az webapp log download \
       --name YOUR_APP_NAME \
       --resource-group YOUR_RESOURCE_GROUP \
       --log-file /tmp/webapp_logs.zip

   # Extract and read
   unzip /tmp/webapp_logs.zip -d /tmp/logs
   cat /tmp/logs/LogFiles/*default_docker.log | tail -100
   ```

2. **Look for Python import errors:**
   Common errors include:
   ```
   ModuleNotFoundError: No module named 'src.api'
   ModuleNotFoundError: No module named 'src.parsers'
   ImportError: cannot import name 'app' from 'src.api'
   ```

3. **Check the startup command:**
   ```bash
   az webapp config show \
       --name YOUR_APP_NAME \
       --resource-group YOUR_RESOURCE_GROUP \
       --query "{startupCommand:appCommandLine, pythonVersion:linuxFxVersion}"
   ```

**Solution: Robust Import Path Handling**

The fix requires proper Python path configuration in both the entry point and API module.

**Step 1: Create `app.py` (Azure entry point)**

```python
# app.py - Azure App Service entry point
import sys
import os

# Get the directory containing this file
app_dir = os.path.dirname(os.path.abspath(__file__))

# Add the app directory to Python path (for 'src' imports)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Add the src directory to Python path (for 'parsers', 'inference' imports)
src_dir = os.path.join(app_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the FastAPI app
from src.api.medical_invoice_api import app

# Expose the app for uvicorn
__all__ = ["app"]
```

**Step 2: Update `src/api/medical_invoice_api.py` imports**

```python
import sys
from pathlib import Path

# Add paths for imports - handle both local dev and Azure deployment
_this_file = Path(__file__).resolve()
_api_dir = _this_file.parent      # src/api
_src_dir = _api_dir.parent        # src
_project_root = _src_dir.parent   # project root

# Add both src and project root to path for maximum compatibility
for _path in [str(_src_dir), str(_project_root)]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Import with explicit error handling
try:
    # Try direct import from src directory (when src is in path)
    from parsers.medical_invoice_parser import MedicalInvoiceParser
    from inference.config import InferenceSettings
    from inference.inference_service import InferenceService
except ImportError as e1:
    try:
        # Try with src prefix (when project root is in path)
        from src.parsers.medical_invoice_parser import MedicalInvoiceParser
        from src.inference.config import InferenceSettings
        from src.inference.inference_service import InferenceService
    except ImportError as e2:
        import logging
        logging.error(f"Import attempt 1 failed: {e1}")
        logging.error(f"Import attempt 2 failed: {e2}")
        logging.error(f"sys.path: {sys.path}")
        raise ImportError(f"Could not import parser modules. Path: {sys.path}") from e2
```

**Step 3: Fix circular imports in `src/api/__init__.py`**

```python
# src/api/__init__.py
"""API module for medical invoice parsing service"""
# Note: Import app directly from medical_invoice_api module to avoid circular imports
__all__ = ["app"]
```

**Step 4: Set startup command**

```bash
az webapp config set \
    --name YOUR_APP_NAME \
    --resource-group YOUR_RESOURCE_GROUP \
    --startup-file "python -m uvicorn app:app --host 0.0.0.0 --port 8000"
```

**Step 5: Ensure `requirements.txt` exists**

Azure App Service doesn't have `uv` pre-installed. Export dependencies:

```bash
uv export --group api --group llm --no-dev --no-hashes > requirements.txt
```

**Step 6: Redeploy**

```bash
git add -A
git commit -m "Fix Azure import paths"
git push azure main
```

##### Understanding Azure's Oryx Build System

Azure App Service uses Oryx for Python deployments:

1. **Source extraction:** Code is copied to `/tmp/<random>/`
2. **Virtual env creation:** Creates `antenv` in the extraction directory
3. **Dependency installation:** Runs `pip install -r requirements.txt`
4. **Compression:** Compresses output to `/home/site/wwwroot/output.tar.gz`
5. **Runtime extraction:** Extracts to a new temp directory for each container start
6. **PYTHONPATH override:** Sets path to virtual env site-packages

This means:
- `/home/site/wwwroot` contains compressed code, NOT the actual runtime files
- Each container restart extracts to a NEW temp path
- `sys.path` manipulations in your code must handle this dynamic path

##### Verification

After deployment, verify the app is working:

```bash
# Check health endpoint
curl https://YOUR_APP_NAME.azurewebsites.net/health

# Test parse endpoint
curl -X POST "https://YOUR_APP_NAME.azurewebsites.net/parse?inference=true" \
    -F "file=@invoice.pdf"
```

Expected health response:
```json
{"status":"healthy","service":"medical-invoice-parser","version":"1.0.0"}
```

---

## Appendix A: File Reference

| File | Purpose |
|------|---------|
| `app.py` | Azure App Service entry point (path configuration) |
| `requirements.txt` | Dependencies for Azure (generated from uv) |
| `src/parsers/medical_invoice_parser.py` | Core parsing logic |
| `src/api/medical_invoice_api.py` | FastAPI service |
| `src/inference/__init__.py` | Inference module exports |
| `src/inference/config.py` | InferenceSettings (env configuration) |
| `src/inference/models.py` | Pydantic models for inference results |
| `src/inference/keyword_matcher.py` | Rule-based keyword matching |
| `src/inference/slm_client.py` | OpenAI GPT-4o-mini client |
| `src/inference/inference_service.py` | Inference orchestrator |
| `resources/jsonTemplates/claimSubmitTemplate.json` | Basic template (v1) |
| `resources/jsonTemplates/claimSubmitTemplate2.json` | Enhanced template with keywords (v2) |
| `.env.example` | Configuration template |
| `gui/index.html` | Test interface |
| `notebooks/test_medical_invoice_parser.ipynb` | Test notebook |

---

## Appendix B: Quick Reference

### Start Server
```bash
uv run uvicorn src.api.medical_invoice_api:app --reload
```

### Parse Invoice (Without Inference)
```bash
curl -X POST http://localhost:8000/parse -F "file=@invoice.pdf"
```

### Parse Invoice (With Inference) - Recommended
```bash
curl -X POST "http://localhost:8000/parse?inference=true" -F "file=@invoice.pdf"
```

### Parse Invoice (Python with Inference)
```python
from src.parsers.medical_invoice_parser import parse_invoice
from src.inference import InferenceService

# Parse
result = parse_invoice("invoice.pdf")

# Infer
service = InferenceService()  # keyword-only mode
inference_result = service.infer(result)

print(f"Diagnosis: {inference_result.diagnosis.code}")
print(f"Benefit: {inference_result.benefit.type_code}")
```

### Get Template
```bash
curl http://localhost:8000/template?version=v2
```

### Configure SLM Fallback
```bash
# Copy example config
cp .env.example .env

# Edit and add your OpenAI API key
# INFERENCE_OPENAI_API_KEY=sk-proj-xxxxx
```

---

## 14. Revision History

This section documents significant changes, refactors, and bug fixes for context and reference.

---

### Version 2.2 - January 2026

#### Azure Deployment Fixes

**1. Azure App Service Import Path Resolution**
- **Files:** `app.py`, `src/api/medical_invoice_api.py`, `src/api/__init__.py`
- **Issue:** Deployment to Azure App Service via Git (Oryx build) resulted in 503 errors with container exit code 1. The container logs showed `ModuleNotFoundError: No module named 'src.api'` or `No module named 'src.parsers'`.
- **Root Cause:** Azure's Oryx build system extracts code to dynamic temp directories (`/tmp/<random>/`) and overrides PYTHONPATH to point to the virtual environment. The original import structure assumed a fixed working directory.
- **Fix:**
  1. Created `app.py` as Azure entry point that explicitly adds both project root and `src/` to `sys.path`
  2. Updated `src/api/medical_invoice_api.py` with fallback imports (try `from parsers...` then `from src.parsers...`)
  3. Removed auto-import from `src/api/__init__.py` to prevent circular import issues
- **Startup Command:** `python -m uvicorn app:app --host 0.0.0.0 --port 8000`
- **Documentation:** Added troubleshooting section in 13.5 with step-by-step debugging guide

**2. Requirements.txt Generation**
- **File:** `requirements.txt`
- **Issue:** Azure App Service doesn't have `uv` pre-installed, so `uv sync` in startup command failed
- **Fix:** Generated `requirements.txt` using `uv export --group api --group llm --no-dev --no-hashes`
- **Note:** Must regenerate when dependencies change

---

### Version 2.1 - January 2026

#### Bug Fixes

**1. Parser State Leakage Fix**
- **File:** `src/parsers/medical_invoice_parser.py`
- **Issue:** When reusing the same `MedicalInvoiceParser` instance for multiple `parse()` calls, the `warnings`, `confidence`, and `requires_review` lists accumulated across invocations, causing inconsistent results and degrading confidence scores.
- **Root Cause:** Instance variables were only initialized in `__init__()`, not reset per parse call.
- **Fix:** Added state reset at the beginning of `parse()`:
  ```python
  def parse(self, pdf_path: str) -> MedicalInvoiceResult:
      # Reset state for each parse call to prevent leakage between invocations
      self.warnings = []
      self.confidence = 1.0
      self.requires_review = []
      # ... rest of method
  ```
- **Test Coverage:** `tests/test_stress.py::TestParserStress::test_repeated_parsing_no_state_leakage`

**2. Inference Service Null Check**
- **File:** `src/inference/inference_service.py`
- **Issue:** When `parsed_data["extracted"]` was `None` instead of a dict, calling `.get()` on it caused an `AttributeError`.
- **Fix:** Added type checking before accessing extracted data:
  ```python
  extracted = parsed_data.get("extracted") if parsed_data else None
  if not isinstance(extracted, dict):
      extracted = {}
  ```
- **Test Coverage:** `tests/test_stress.py::TestEdgeCaseInputs::test_malformed_parsed_data`

**3. Keyword Matcher Type Safety**
- **File:** `src/inference/keyword_matcher.py`
- **Issue:** When `diagnosisRaw` or `providerName` contained non-string types (e.g., integers), calling `.strip()` raised an `AttributeError`.
- **Fix:** Added `isinstance(value, str)` checks in both `match_diagnosis()` and `match_benefit()`:
  ```python
  if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
      return DiagnosisInference(method=InferenceMethod.NOT_ATTEMPTED, ...)
  ```
- **Test Coverage:** `tests/test_stress.py::TestEdgeCaseInputs::test_diagnosis_edge_cases`

#### New Features

**1. Test Suite Implementation**
- **Files:** `tests/conftest.py`, `tests/test_parser.py`, `tests/test_inference.py`, `tests/test_stress.py`, `tests/test_api.py`
- **Purpose:** Comprehensive test coverage for parser, inference layer, and API
- **Test Categories:**
  - **Parser Tests (16 tests):** Basic extraction, confidence scoring, edge cases, date formats, amount calculations
  - **Inference Tests (32 tests):** Keyword matching accuracy, confidence scoring, method transparency, HITL flagging
  - **Stress Tests (34 tests):** State leakage, batch processing, concurrency, memory usage, malformed input handling
  - **API Tests (20+ tests):** Endpoint availability, request/response formats, inference parameter, CORS
- **Run Command:** `uv run pytest tests/ -v`

**2. GUI Inference Support**
- **File:** `gui/index.html`
- **Changes:**
  - Added "Enable Inference Layer" checkbox (enabled by default)
  - Dynamic API endpoint display (`POST /parse?inference=true`)
  - New "Inference Results" section showing diagnosis and benefit inferences
  - Method badges (Keyword/SLM/HITL) with color coding
  - Confidence bars with visual indicators
  - Renamed "Requires Inference" to "Human Review Required" for clarity

---

### Version 2.0 - January 2026

#### New Features

**1. Inference Layer Implementation**
- **Files:** `src/inference/__init__.py`, `src/inference/config.py`, `src/inference/models.py`, `src/inference/keyword_matcher.py`, `src/inference/slm_client.py`, `src/inference/inference_service.py`
- **Purpose:** Resolve `diagnosisCode`, `benefitType`, and `benefitCategory` from PDF content using a layered approach
- **Architecture:**
  ```
  Raw Text → Keyword Matching (fast, free) → SLM Fallback (GPT-4o-mini) → HITL Flag
  ```
- **Method Transparency:** Each inferred field includes `method` (keyword_match/slm/hitl_required) and `confidence` score
- **Configuration:** Environment variables with `INFERENCE_` prefix (see `.env.example`)

**2. API Inference Parameter**
- **File:** `src/api/medical_invoice_api.py`
- **Change:** Added `?inference=true` query parameter to `/parse` and `/parse/base64` endpoints
- **Backward Compatible:** Without the parameter, response excludes `inferred` section

**3. Responsibility Boundary Clarification**
- **Documented:** Clear separation between what parser+inference resolves vs what upstream agent must provide
- **Parser Resolves:** All fields derivable from PDF content
- **Upstream Agent Provides:** Employee ID, department, email, date of claim, attachments

---

### Version 1.0 - January 2026

#### Initial Release

- **Core Parser:** `src/parsers/medical_invoice_parser.py`
  - PyMuPDF-based text extraction
  - Multi-format support (City Osteopathy style, OneDoctors style)
  - Confidence scoring and warning generation
  - Fields requiring review flagging

- **API Service:** `src/api/medical_invoice_api.py`
  - FastAPI-based REST API
  - File upload (`/parse`) and base64 (`/parse/base64`) endpoints
  - Template endpoints for claim structure reference
  - Health check endpoint

- **GUI:** `gui/index.html`
  - Drag-and-drop PDF upload
  - Real-time extraction results display
  - Raw JSON view toggle

---

### File Change Summary

| Version | Files Added | Files Modified |
|---------|-------------|----------------|
| 2.2 | `app.py`, `requirements.txt` | `src/api/medical_invoice_api.py`, `src/api/__init__.py`, `MEDICAL_PARSER_GUIDE.md` |
| 2.1 | `tests/conftest.py`, `tests/test_parser.py`, `tests/test_inference.py`, `tests/test_stress.py`, `tests/test_api.py`, `scripts/run_tests.py` | `src/parsers/medical_invoice_parser.py`, `src/inference/inference_service.py`, `src/inference/keyword_matcher.py`, `gui/index.html` |
| 2.0 | `src/inference/*.py` (6 files), `.env.example` | `src/api/medical_invoice_api.py`, `gui/index.html`, `MEDICAL_PARSER_GUIDE.md` |
| 1.0 | Initial codebase | — |

---

### Known Issues & Technical Debt

1. **Keyword Priority:** When provider name contains both "dental" and "clinic", the first match wins. Consider weighted scoring for overlapping keywords.
2. **SLM Fallback:** Currently synchronous; consider async implementation for high-throughput scenarios.
3. **Test Data:** API integration tests require running server; consider test fixtures or mocking.

---

**End of Medical Parser Guide v2.2**
