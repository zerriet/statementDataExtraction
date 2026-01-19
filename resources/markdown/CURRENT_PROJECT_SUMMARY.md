# Current Project Summary

**Project:** Statement Data Extraction
**Version:** 1.0
**Date:** January 2026
**Branch:** feature/medicalParsing
**Status:** Phase 1 Complete (Bank Statements) | Phase 2 In Progress (Medical Invoices)

---

## 1. Executive Overview

### Purpose
This project implements a **defensive, deterministic PDF parser** for extracting structured transaction data from semi-structured financial documents. The system follows maker-checker principles, prioritizing accuracy, transparency, and human oversight over full automation.

### Current Capabilities
- **Bank Statement Parsing**: DBS Singapore statements (production-ready, 100% accuracy)
- **Medical Invoice Parsing**: In development (feature/medicalParsing branch)

### Core Philosophy
- **Defensive by Default**: Treat PDFs as hostile, semi-graphical artifacts
- **Fail Transparently**: Prefer explicit failure over silent errors
- **Cost-Aware Automation**: Use expensive parsing only when required
- **Human Authority**: Humans retain final approval rights

---

## 2. Project Architecture

### Directory Structure
```
statementDataExtraction/
├── src/
│   ├── parsers/
│   │   └── deterministic_parser.py      # Core extraction engine (531 lines)
│   └── diagnostics/
│       ├── analyze_pdf_coordinates.py    # Column boundary discovery tool
│       └── inspect_transaction.py        # Transaction area inspection
│
├── resources/
│   ├── docs/                             # FSD and TSD specifications
│   ├── markdown/                         # Development documentation
│   ├── articles/                         # PDF structure reference materials
│   ├── referenceMaterials/               # Mermaid diagrams
│   └── statements/
│       ├── bank_statements/              # Bank statement test data
│       └── medical_invoice_statements/   # Medical invoice test data
│
├── extracted_data/                       # Output directory
├── notebooks/                            # Jupyter notebooks (planned)
├── validate_extraction.py                # Validation script
├── pyproject.toml                        # Dependencies & project config
└── README.md
```

### Technology Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.11+ | Primary implementation |
| PDF Processing | PyMuPDF (fitz) | Coordinate-based text extraction |
| Data Validation | Pandas, Pydantic | Structure & schema validation |
| Async Processing | Celery + Redis | Background tasks (Phase 2+) |
| Vision/OCR | Docling | Vision-based fallback (Phase 2+) |
| Web Framework | FastAPI | REST API (Phase 2+) |

---

## 3. Functional Requirements (FSD)

### FR-1: Ingestion & Risk Assessment
- Assess document integrity and text reliability
- Route high-risk documents to robust parsing paths
- **Status**: Implemented

### FR-2: Hybrid Parsing
- Deterministic text-based parsing (primary)
- Vision-based document understanding (fallback)
- **Status**: Deterministic complete, Vision planned

### FR-3: Automated Validation
- Arithmetic consistency checks
- Mandatory field presence validation
- Currency and date normalization
- **Status**: Partial (balance validation implemented)

### FR-4: Human-in-the-Loop Review
- Documents below confidence thresholds require human approval
- Auditable review actions
- **Status**: Data structured for HITL, UI not implemented

### FR-5: Confidence-Based Decisioning
- Document-level confidence scoring (0.0-1.0)
- Confidence governs auto-approval, review, or rejection
- **Status**: Implemented

---

## 4. Technical Implementation (TSD)

### 4.1 Ingestion Guard
```python
def _validate_document(self, doc) -> bool:
    # Text layer integrity checks
    # Coordinate normalization
    # Expected header validation ("Transaction Details" or "Account Summary")
    # Returns: bool (pass/fail)
```
**Status**: Implemented

### 4.2 Routing Engine
- Template fingerprint matching
- Threshold-based parser selection
- **Status**: Not yet implemented

### 4.3 Deterministic Parser
The core extraction engine with the following capabilities:
- **Word Grouping**: Y-coordinate grouping (3px tolerance)
- **Column Detection**: X-coordinate based classification
- **Continuation Lines**: Multi-line amount/description handling
- **Span Merging**: Kerning correction
- **Explicit Abort**: Clear failure semantics

**Column Boundaries (DBS Singapore)**:
| Column | X-Position Range |
|--------|------------------|
| Date | x < 55 |
| Description | 103 < x < 364 |
| Withdrawal | 364 < x < 440 |
| Deposit | 440 < x < 503 |
| Balance | x > 503 |

**Status**: Complete and production-ready

### 4.4 Vision Parser Integration
- External vision engine invocation (Docling)
- Output normalization layer
- Confidence and warning propagation
- **Status**: Not yet implemented

### 4.5 Validation Engine
- Arithmetic consistency checks
- Semantic validation
- **Status**: Partial (balance continuity validated)

### 4.6 Human Review Interface
- Bounding box overlays
- Field-level correction support
- Audit logging
- **Status**: Data structured, UI not implemented

---

## 5. Data Models

### ParserResult (Output Structure)
```python
@dataclass
class ParserResult:
    success: bool                    # Extraction success/failure
    data: List[Dict]                 # Extracted transactions
    confidence: float                # 0.0-1.0 confidence score
    warnings: List[str]              # Non-fatal issues
    abort_reason: Optional[str]      # Explicit failure reason
```

### Transaction Schema
```json
{
    "date": "01/01/2022",            // DD/MM/YYYY format
    "description": "...",             // Full transaction text
    "withdrawal": 20.00,              // Outgoing amount (null if none)
    "deposit": null,                  // Incoming amount (null if none)
    "balance": 7980.00,               // Running balance
    "page": 2                         // Source page number
}
```

### Output File Structure (extracted_data.json)
```json
{
    "success": true,
    "confidence": 1.0,
    "warnings": ["Could not find transaction table on page 1"],
    "transaction_count": 117,
    "data": [/* array of transactions */]
}
```

---

## 6. Parsing Algorithm

### High-Level Flow
```
PDF Input
    |
    v
[Ingestion Guard] --> Validate text layer integrity
    |
    v
[Page Iterator] --> For each page in document
    |
    v
[Word Extraction] --> PyMuPDF get_text("words")
    |                  Returns: (x0, y0, x1, y1, text, block, line, word)
    v
[Y-Coordinate Grouping] --> Merge words within 3px vertically
    |
    v
[Table Boundary Detection] --> Find "CURRENCY:" or first date pattern
    |
    v
[Transaction Parsing] --> For each line:
    |                     - Detect transaction start (DD/MM/YYYY)
    |                     - Classify amounts by x-coordinate
    |                     - Handle continuation lines
    |                     - Build description from text words
    v
[Post-Processing] --> Remove "Balance Brought/Carried Forward" entries
    |
    v
[Output] --> ParserResult with transactions + confidence + warnings
```

### Critical Implementation Details

**1. Word Grouping (Y-Coordinate)**
```python
# Words within 3 pixels vertically belong to same line
line_key = round(y0 / 3) * 3
```

**2. Amount Classification (X-Coordinate)**
```python
if x_pos > 503:
    balance = amount        # Rightmost column
elif x_pos > 440:
    deposit = amount        # Middle-right column
elif x_pos > 364:
    withdrawal = amount     # Middle-left column
```

**3. Continuation Line Processing**
- Amounts can appear on separate lines (Y offset ~3px)
- Parser checks non-date lines for amounts
- Merges into parent transaction if field is null

---

## 7. Current Test Results

### DBS Singapore Bank Statement
| Metric | Value |
|--------|-------|
| Pages Processed | 13 |
| Transactions Extracted | 117 |
| Success Rate | 100% |
| Confidence Score | 1.0 |
| Opening Balance | SGD 8,000.00 |
| Closing Balance | SGD 9,754.64 |
| Balance Accuracy | 100% match |

### Validation Summary
- Date Extraction: 100% accurate
- Description Extraction: 100% (including multi-line)
- Withdrawal Classification: 100% accurate
- Deposit Classification: 100% accurate
- Balance Values: 100% match with PDF

---

## 8. Key Design Decisions

### Why X-Coordinate Based Column Detection?
- **Problem**: Keyword-based classification ("INCOMING", "WITHDRAWAL") was unreliable
- **Solution**: Analyzed actual PDF coordinates using diagnostic tools
- **Result**: 100% accuracy by using position-based column boundaries

### Why Y-Coordinate Word Grouping?
- **Problem**: PDF text extraction returns individual words, not lines
- **Solution**: Group words within 3px vertical tolerance
- **Result**: Reconstructs logical lines for transaction parsing

### Why Continuation Line Processing?
- **Problem**: Some amounts appear on separate lines below transaction header
- **Discovery**: Diagnostic tool revealed amounts 3px below main line
- **Solution**: Check non-date lines for amounts, merge into parent transaction

### Why Defensive Parsing?
- **Context**: Financial documents have legal/regulatory implications
- **Approach**: Explicit failure > silent errors
- **Implementation**: Confidence scoring, warnings, abort semantics

---

## 9. Dependencies

### Core (pyproject.toml)
```toml
[project]
requires-python = ">=3.11,<3.13"

[project.dependencies]
pymupdf = ">=1.24.5"
pandas = ">=2.2.0"
numpy = ">=1.26.4"
pydantic-settings = ">=2.2.1"
```

### Optional Groups
- **api**: FastAPI, uvicorn, python-multipart
- **worker**: Celery, Redis, Docling
- **llm**: Instructor, OpenAI (Phase 3)
- **dev**: pytest, ruff, jupyter, ipykernel

---

## 10. Roadmap & Phase Status

### Phase 1: Proof of Concept (COMPLETE)
- [x] Deterministic text-based parsing
- [x] DBS Singapore statement support
- [x] Manual validation via scripts
- [x] 100% accuracy on test data
- [x] Confidence scoring
- [x] Defensive error handling

### Phase 2: Hybrid Parsing (IN PROGRESS)
- [ ] Medical invoice parsing (current branch)
- [ ] Vision-augmented parsing (Docling)
- [ ] FastAPI ingestion layer
- [ ] Celery async processing
- [ ] Multi-bank support

### Phase 3: Production (PLANNED)
- [ ] Auto-approval for high-confidence documents
- [ ] LLM-based schema normalization
- [ ] Human review UI
- [ ] Audit trail and versioning
- [ ] Template governance

---

## 11. Extension Points for New Use Cases

### Adding a New Document Type
1. **Analyze Document Structure**
   - Use `analyze_pdf_coordinates.py` to discover column boundaries
   - Use `inspect_transaction.py` to examine specific areas

2. **Define Column Boundaries**
   - Map x-coordinate ranges to data columns
   - Document expected patterns (date format, amount format)

3. **Implement Parser Logic**
   - Create table boundary detection for new document type
   - Define transaction start/end patterns
   - Handle document-specific continuation patterns

4. **Validate Output**
   - Create validation script with known ground truth
   - Verify all fields extracted correctly
   - Check confidence scoring

### Adding Vision Parser Fallback
1. Integrate Docling for OCR/vision processing
2. Define confidence threshold for fallback trigger
3. Normalize vision output to match deterministic schema
4. Merge confidence scores from both paths

### Adding New Validation Rules
1. Arithmetic consistency: balance[n] = balance[n-1] - withdrawal + deposit
2. Date continuity: transactions in chronological order
3. Duplicate detection: flag identical transactions
4. Amount bounds: validate reasonable value ranges

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| DBS Singapore only | Cannot parse other banks | Planned multi-bank support |
| Fixed column positions | Assumes consistent layout | Vision fallback (Phase 2) |
| DD/MM/YYYY date format | Other formats not supported | Add format detection |
| SGD currency only | No multi-currency | Add currency detection |
| No HITL UI | Manual review via JSON | Build review interface |
| No vision fallback | Complex layouts may fail | Docling integration (Phase 2) |

---

## 13. File Reference Guide

### Core Implementation
| File | Purpose | Lines |
|------|---------|-------|
| [src/parsers/deterministic_parser.py](src/parsers/deterministic_parser.py) | Main extraction engine | 531 |
| [validate_extraction.py](validate_extraction.py) | Output validation | 107 |

### Diagnostic Tools
| File | Purpose |
|------|---------|
| [src/diagnostics/analyze_pdf_coordinates.py](src/diagnostics/analyze_pdf_coordinates.py) | Discover column boundaries |
| [src/diagnostics/inspect_transaction.py](src/diagnostics/inspect_transaction.py) | Inspect specific PDF areas |

### Specification Documents
| File | Purpose |
|------|---------|
| [resources/docs/...fsd...md](resources/docs/functional_specification_document_fsd_defensive_income_statement_parser.md) | Functional requirements |
| [resources/docs/...tsd...md](resources/docs/technical_specification_document_tsd_defensive_income_statement_parser.md) | Technical implementation |

### Development Documentation
| File | Purpose |
|------|---------|
| [resources/markdown/DEVELOPMENT_SUMMARY.md](resources/markdown/DEVELOPMENT_SUMMARY.md) | Complete development history |
| [resources/markdown/EXTRACTION_SUMMARY.md](resources/markdown/EXTRACTION_SUMMARY.md) | Extraction results report |

### Reference Materials
| Folder | Contents |
|--------|----------|
| resources/articles/ | PDF structure articles (5 documents) |
| resources/referenceMaterials/ | Mermaid diagrams |

---

## 14. Context for LLM Use Cases

### What This Project Does Well
1. **Coordinate-based extraction**: Precise position-based parsing
2. **Defensive design**: Explicit failure semantics
3. **Structured output**: JSON with confidence and warnings
4. **Validation-ready**: Data structured for downstream checks
5. **Well-documented**: FSD, TSD, and development history

### Potential Enhancement Areas
1. **Multi-document support**: Additional bank formats, medical invoices
2. **Vision integration**: Docling for complex/scanned documents
3. **LLM augmentation**: Schema normalization, entity extraction
4. **Validation engine**: Arithmetic and semantic checks
5. **HITL interface**: Human review and correction UI

### Recommended Prompts for New Use Cases
- "Extend the parser to support [new document type]"
- "Implement vision parser fallback using Docling"
- "Add arithmetic validation to verify transaction balances"
- "Create a human review interface for low-confidence extractions"
- "Add support for multi-currency transactions"

---

## 15. Quick Start for Developers

### Setup
```bash
# Clone and setup
cd statementDataExtraction
uv sync  # or pip install -e .

# Run parser
python -c "
from src.parsers.deterministic_parser import DeterministicBankStatementParser
parser = DeterministicBankStatementParser()
result = parser.parse('resources/statements/your-statement.pdf')
print(f'Success: {result.success}, Transactions: {len(result.data)}')
"
```

### Validate Output
```bash
python validate_extraction.py
```

### Analyze New Document
```bash
# Discover column boundaries
python src/diagnostics/analyze_pdf_coordinates.py

# Inspect specific area
python src/diagnostics/inspect_transaction.py
```

---

**End of Current Project Summary**
