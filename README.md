# Bank Statement Data Extraction

A defensive, multi-phase bank statement parser designed with maker-checker principles for safe, reliable data extraction from PDF bank statements.

## Overview

This project implements a deterministic parser for extracting transaction data from bank statement PDFs (currently focused on DBS Singapore statements). Built with defensive programming principles, it prioritizes accuracy, transparency, and human oversight over automation.

**Key Features:**
- **Deterministic parsing** using coordinate-based table extraction
- **Confidence scoring** with explicit warning systems
- **Defensive architecture** with abort semantics for low-quality extractions
- **Multi-phase design** supporting progressive enhancement (text → vision → LLM)
- **Jupyter notebook** interface for interactive testing and validation

## Project Architecture

### Core Components

```
src/
├── parsers/
│   └── deterministic_parser.py    # Main text-based PDF parser
└── diagnostics/
    ├── analyze_pdf_coordinates.py  # PDF structure analysis tools
    └── inspect_transaction.py      # Transaction debugging utilities

notebooks/
└── test_deterministic_parser.ipynb  # Interactive testing & validation

resources/
└── statements/                      # Sample bank statements (gitignored)
```

### Technology Stack

- **PDF Processing**: PyMuPDF (fitz) for coordinate-based text extraction
- **Data Validation**: Pandas, NumPy for arithmetic consistency checks
- **Configuration**: Pydantic for schema validation
- **Development**: Jupyter notebooks for interactive testing
- **Future Extensions**: FastAPI (API layer), Celery (async processing), Docling (vision parsing)

## Features

### Deterministic Parser

The core parser (`DeterministicBankStatementParser`) implements:

- **Span Merging**: Corrects kerning issues in PDF text extraction
- **Coordinate-Based Extraction**: Precise table boundary detection
- **Defensive Abort Logic**: Explicitly rejects low-quality extractions
- **Confidence Scoring**: Provides transparency about extraction quality
- **Warning System**: Flags anomalies without failing the entire extraction

### Extracted Data Structure

Each transaction contains:
- **Date**: Transaction date (DD/MM/YYYY format)
- **Description**: Full transaction description
- **Withdrawal**: Amount debited (if applicable)
- **Deposit**: Amount credited (if applicable)
- **Balance**: Account balance after transaction
- **Page**: Source page number in PDF

### Validation Features

The parser includes built-in validation:
- Balance arithmetic continuity checks
- Transaction count verification
- Page boundary detection
- Missing field warnings

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- UV package manager (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/zerriet/statementDataExtraction.git
cd statementDataExtraction

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install base dependencies
uv pip install -e .

# Install development dependencies (includes Jupyter)
uv pip install -e . --group dev
```

### Quick Start

#### Using Python Script

```python
from src.parsers.deterministic_parser import DeterministicBankStatementParser

# Initialize parser
parser = DeterministicBankStatementParser()

# Parse bank statement
result = parser.parse("path/to/statement.pdf")

# Check results
print(f"Success: {result.success}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Transactions: {len(result.data)}")
print(f"Warnings: {result.warnings}")

# Access transaction data
for txn in result.data:
    print(f"{txn['date']}: {txn['description']} - Balance: {txn['balance']}")
```

#### Using Jupyter Notebook

```bash
# Start Jupyter
jupyter notebook

# Open notebooks/test_deterministic_parser.ipynb
# Follow the interactive examples for:
# - Basic parsing and extraction
# - Data analysis with pandas
# - Transaction filtering and search
# - Balance validation
# - Export to JSON
```

### Validation Script

```bash
# Run validation on extracted data
python validate_extraction.py
```

## Usage Examples

### Extract All Deposits

```python
import pandas as pd

# Parse and convert to DataFrame
result = parser.parse("statement.pdf")
df = pd.DataFrame(result.data)

# Filter deposits
deposits = df[df['deposit'].notna()]
print(f"Total deposits: SGD {deposits['deposit'].sum():.2f}")
```

### Find Large Transactions

```python
# Find withdrawals over $100
large_withdrawals = df[df['withdrawal'] > 100]
print(large_withdrawals[['date', 'description', 'withdrawal']])
```

### Search by Keyword

```python
# Search for PayNow transactions
paynow_txns = df[df['description'].str.contains('PAYNOW', case=False)]
print(f"Found {len(paynow_txns)} PayNow transactions")
```

### Validate Balance Continuity

```python
# Check balance arithmetic
for i in range(1, len(df)):
    prev_balance = df.iloc[i-1]['balance']
    expected = prev_balance - (df.iloc[i]['withdrawal'] or 0) + (df.iloc[i]['deposit'] or 0)
    actual = df.iloc[i]['balance']

    if abs(expected - actual) > 0.01:
        print(f"Discrepancy at row {i}: Expected {expected:.2f}, Got {actual:.2f}")
```

## Development

### Project Structure

The project follows a defensive, maker-checker architecture:

**Phase 1 (Current)**: Deterministic text-based parsing
- Text extraction using PyMuPDF
- Coordinate-based table detection
- Manual validation via Jupyter notebooks

**Phase 2 (Planned)**: Vision-augmented parsing
- Docling integration for complex layouts
- Hybrid text + vision approach
- FastAPI ingestion layer

**Phase 3 (Future)**: LLM-augmented normalization
- Schema standardization (not primary extraction)
- Confidence-based decisioning
- Always with human review

### Running Tests

```bash
# Install test dependencies
uv pip install -e . --group dev

# Run tests (when available)
pytest
```

### Code Quality

```bash
# Run linter
ruff check src/

# Format code
ruff format src/
```

## Current Limitations

- **Bank Support**: Currently optimized for DBS Singapore statements only
- **Format Assumptions**: Requires consistent table structure across pages
- **Date Format**: Expects DD/MM/YYYY format
- **Currency**: Assumes SGD (no multi-currency support)
- **Page Headers**: May struggle with statements having complex headers/footers

## Roadmap

- [ ] Multi-bank support (OCBC, UOB, Citibank)
- [ ] Vision parser integration for complex layouts
- [ ] FastAPI REST API for programmatic access
- [ ] Background processing with Celery
- [ ] PDF quality pre-checks (ingestion guard)
- [ ] Enhanced validation rules (date continuity, duplicate detection)
- [ ] Export to multiple formats (CSV, Excel, Parquet)
- [ ] LLM-based schema normalization (Phase 3)

## Contributing

This is currently a personal portfolio project, but suggestions and feedback are welcome! Please open an issue to discuss potential improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**zerriet**

## Acknowledgments

- Built with defensive programming principles inspired by financial engineering practices
- Uses PyMuPDF for robust PDF text extraction
- Pandas for data validation and analysis

## Disclaimer

This tool is for personal financial record-keeping and analysis only. Always verify extracted data against original statements. The author assumes no liability for financial decisions made based on extracted data.

---

**Note**: This project demonstrates proficiency in:
- Defensive software design patterns
- PDF processing and text extraction
- Data validation and quality assurance
- Financial data handling
- Python best practices
- Documentation and testing
