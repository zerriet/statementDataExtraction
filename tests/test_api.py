"""
Integration tests for Medical Invoice Parser API.

Tests:
- Endpoint availability
- Request/response formats
- Inference query parameter
- Error handling
- CORS headers

Requires running server: uv run uvicorn src.api.medical_invoice_api:app --reload
"""

import pytest
import httpx
import base64
from pathlib import Path

API_URL = "http://127.0.0.1:8000"
TEST_DATA_DIR = Path(__file__).parent.parent / "resources" / "statements" / "medical_invoice_statements"


def is_server_running():
    """Check if the API server is running."""
    try:
        response = httpx.get(f"{API_URL}/health", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# Skip all tests if server not running
pytestmark = pytest.mark.skipif(
    not is_server_running(),
    reason="API server not running. Start with: uv run uvicorn src.api.medical_invoice_api:app --reload"
)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self):
        """Health endpoint should return 200."""
        response = httpx.get(f"{API_URL}/health")
        assert response.status_code == 200

    def test_health_returns_correct_structure(self):
        """Health response should have expected fields."""
        response = httpx.get(f"{API_URL}/health")
        data = response.json()

        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert data["status"] == "healthy"


class TestTemplateEndpoint:
    """Tests for /template endpoints."""

    def test_template_default_returns_v2(self):
        """Default template should be v2."""
        response = httpx.get(f"{API_URL}/template")
        assert response.status_code == 200

        data = response.json()
        assert "_enums" in data  # v2 has _enums
        assert "benefitCategory" in data["_enums"]

    def test_template_v1_no_enums(self):
        """v1 template should not have _enums."""
        response = httpx.get(f"{API_URL}/template?version=v1")
        assert response.status_code == 200

        data = response.json()
        assert "_enums" not in data

    def test_template_invalid_version(self):
        """Invalid version should return 400."""
        response = httpx.get(f"{API_URL}/template?version=v99")
        assert response.status_code == 400

    def test_template_list(self):
        """Template list should show available versions."""
        response = httpx.get(f"{API_URL}/template/list")
        assert response.status_code == 200

        data = response.json()
        assert "available" in data
        assert "v1" in data["available"]
        assert "v2" in data["available"]


class TestParseEndpoint:
    """Tests for /parse endpoint (file upload)."""

    def test_parse_invoice_success(self):
        """Should successfully parse a valid invoice."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice1.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse", files=files)

        assert response.status_code == 200
        data = response.json()

        assert "extracted" in data
        assert "metadata" in data
        assert data["metadata"]["success"] is True

    def test_parse_without_inference(self):
        """Without inference param, should not include 'inferred' section."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice1.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse", files=files)

        data = response.json()
        assert "inferred" not in data

    def test_parse_with_inference(self):
        """With inference=true, should include 'inferred' section."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice1.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse?inference=true", files=files)

        data = response.json()
        assert "inferred" in data
        assert data["inferred"]["inference_attempted"] is True

    def test_parse_with_inference_has_diagnosis(self):
        """Inferred section should include diagnosis."""
        invoice_path = TEST_DATA_DIR / "invoice2.pdf"  # Has diagnosis
        if not invoice_path.exists():
            pytest.skip("invoice2.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice2.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse?inference=true", files=files)

        data = response.json()
        assert "inferred" in data
        assert "diagnosis" in data["inferred"]
        assert "method" in data["inferred"]["diagnosis"]

    def test_parse_with_inference_has_benefit(self):
        """Inferred section should include benefit."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice1.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse?inference=true", files=files)

        data = response.json()
        assert "inferred" in data
        assert "benefit" in data["inferred"]
        assert "method" in data["inferred"]["benefit"]

    def test_parse_rejects_non_pdf(self):
        """Should reject non-PDF files."""
        response = httpx.post(
            f"{API_URL}/parse",
            files={"file": ("test.txt", b"not a pdf", "text/plain")}
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]


class TestParseBase64Endpoint:
    """Tests for /parse/base64 endpoint."""

    def test_parse_base64_success(self):
        """Should successfully parse base64-encoded PDF."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        response = httpx.post(
            f"{API_URL}/parse/base64",
            json={"file_content": content, "filename": "invoice1.pdf"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["success"] is True

    def test_parse_base64_with_inference(self):
        """Should support inference param."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        response = httpx.post(
            f"{API_URL}/parse/base64?inference=true",
            json={"file_content": content, "filename": "invoice1.pdf"}
        )

        data = response.json()
        assert "inferred" in data

    def test_parse_base64_invalid_encoding(self):
        """Should reject invalid base64."""
        response = httpx.post(
            f"{API_URL}/parse/base64",
            json={"file_content": "not-valid-base64!!!", "filename": "test.pdf"}
        )

        assert response.status_code == 400

    def test_parse_base64_not_pdf_content(self):
        """Should reject non-PDF content."""
        content = base64.b64encode(b"This is not a PDF file").decode()

        response = httpx.post(
            f"{API_URL}/parse/base64",
            json={"file_content": content, "filename": "test.pdf"}
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]


class TestCORS:
    """Tests for CORS headers."""

    def test_cors_headers_present(self):
        """CORS headers should be present."""
        response = httpx.options(
            f"{API_URL}/parse",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestResponseConsistency:
    """Tests for response format consistency."""

    def test_all_invoices_same_structure(self):
        """All invoice responses should have same structure."""
        invoice_files = list(TEST_DATA_DIR.glob("*.pdf"))
        if not invoice_files:
            pytest.skip("No invoice PDFs found")

        required_extracted_fields = [
            "invoiceNumber", "visitDate", "providerName",
            "lineItems", "paymentAmount", "currency"
        ]

        for pdf_path in invoice_files:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = httpx.post(f"{API_URL}/parse", files=files)

            if response.status_code == 200:
                data = response.json()
                for field in required_extracted_fields:
                    assert field in data["extracted"], \
                        f"Missing '{field}' in {pdf_path.name}"

    def test_inference_response_structure(self):
        """Inference response should have consistent structure."""
        invoice_path = TEST_DATA_DIR / "invoice1.pdf"
        if not invoice_path.exists():
            pytest.skip("invoice1.pdf not found")

        with open(invoice_path, "rb") as f:
            files = {"file": ("invoice1.pdf", f, "application/pdf")}
            response = httpx.post(f"{API_URL}/parse?inference=true", files=files)

        data = response.json()
        inferred = data["inferred"]

        # Check diagnosis structure
        assert "code" in inferred["diagnosis"]
        assert "method" in inferred["diagnosis"]
        assert "confidence" in inferred["diagnosis"]

        # Check benefit structure
        assert "category" in inferred["benefit"]
        assert "type_code" in inferred["benefit"]
        assert "method" in inferred["benefit"]

        # Check top-level inference fields
        assert "hitl_required" in inferred
        assert "inference_attempted" in inferred
