"""
Pytest configuration and shared fixtures for Medical Invoice Parser tests.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent / "resources" / "statements" / "medical_invoice_statements"
TEMPLATE_DIR = Path(__file__).parent.parent / "resources" / "jsonTemplates"


@pytest.fixture
def sample_invoice_paths():
    """Return paths to sample invoice PDFs."""
    return list(TEST_DATA_DIR.glob("*.pdf"))


@pytest.fixture
def invoice1_path():
    """Path to invoice1.pdf (City Osteopathy style)."""
    return TEST_DATA_DIR / "invoice1.pdf"


@pytest.fixture
def invoice2_path():
    """Path to invoice2.pdf (OneDoctors style)."""
    return TEST_DATA_DIR / "invoice2.pdf"


@pytest.fixture
def template_v2():
    """Load claimSubmitTemplate2.json."""
    import json
    with open(TEMPLATE_DIR / "claimSubmitTemplate2.json", "r") as f:
        return json.load(f)


@pytest.fixture
def parser():
    """Create a fresh MedicalInvoiceParser instance."""
    from parsers.medical_invoice_parser import MedicalInvoiceParser
    return MedicalInvoiceParser()


@pytest.fixture
def inference_service():
    """Create an InferenceService in keyword-only mode."""
    from inference import InferenceService
    return InferenceService(settings=None)


@pytest.fixture
def keyword_matcher():
    """Create a KeywordMatcher instance."""
    from inference.keyword_matcher import KeywordMatcher
    return KeywordMatcher()


# Mock data for testing
@pytest.fixture
def mock_parsed_data():
    """Sample parsed data for testing inference."""
    return {
        "extracted": {
            "invoiceNumber": "TEST-001",
            "visitDate": "2025-01-15",
            "providerName": "City Osteopathy & Physiotherapy",
            "patientName": "Test Patient",
            "lineItems": [
                {"description": "Physiotherapy Session", "amount": 170.0}
            ],
            "subtotal": 170.0,
            "gstAmount": 15.30,
            "paymentAmount": 185.30,
            "currency": "SGD",
            "diagnosisRaw": "Acute lower back pain"
        },
        "inference_required": [
            "diagnosisCode: no diagnosis code found",
            "benefitType: requires inference from provider name"
        ],
        "metadata": {
            "success": True,
            "confidence": 1.0,
            "warnings": [],
            "source_file": "test.pdf",
            "abort_reason": None
        }
    }


@pytest.fixture
def mock_respiratory_data():
    """Sample parsed data with respiratory diagnosis."""
    return {
        "extracted": {
            "invoiceNumber": "H101494",
            "visitDate": "2025-04-19",
            "providerName": "ONEDOCTORS FAMILY CLINIC",
            "patientName": "MARK TAN",
            "lineItems": [
                {"description": "Consultation", "amount": 35.0},
                {"description": "Medication", "amount": 7.0}
            ],
            "subtotal": 42.0,
            "gstAmount": 3.78,
            "paymentAmount": 45.78,
            "currency": "SGD",
            "diagnosisRaw": "Acute upper respiratory infection"
        },
        "metadata": {
            "success": True,
            "confidence": 1.0,
            "warnings": [],
            "source_file": "invoice2.pdf",
            "abort_reason": None
        }
    }
