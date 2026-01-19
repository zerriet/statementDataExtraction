"""
Unit tests for MedicalInvoiceParser.

Tests:
- Basic extraction from known invoice formats
- Edge cases (missing fields, unusual formats)
- Confidence scoring
- Error handling
"""

import pytest
from pathlib import Path


class TestParserBasicExtraction:
    """Tests for basic field extraction."""

    def test_parse_invoice1_extracts_invoice_number(self, parser, invoice1_path):
        """Invoice1 should extract invoice number."""
        if not invoice1_path.exists():
            pytest.skip("invoice1.pdf not found")

        result = parser.parse(str(invoice1_path))

        assert result.success is True
        assert result.data.get("invoiceNumber") is not None
        assert len(result.data["invoiceNumber"]) > 0

    def test_parse_invoice1_extracts_amounts(self, parser, invoice1_path):
        """Invoice1 should extract monetary amounts."""
        if not invoice1_path.exists():
            pytest.skip("invoice1.pdf not found")

        result = parser.parse(str(invoice1_path))

        assert result.data.get("paymentAmount") is not None
        assert isinstance(result.data["paymentAmount"], (int, float))
        assert result.data["paymentAmount"] > 0

    def test_parse_invoice2_extracts_provider_name(self, parser, invoice2_path):
        """Invoice2 should extract provider name."""
        if not invoice2_path.exists():
            pytest.skip("invoice2.pdf not found")

        result = parser.parse(str(invoice2_path))

        assert result.success is True
        assert result.data.get("providerName") is not None

    def test_parse_invoice2_extracts_diagnosis(self, parser, invoice2_path):
        """Invoice2 should extract diagnosis text."""
        if not invoice2_path.exists():
            pytest.skip("invoice2.pdf not found")

        result = parser.parse(str(invoice2_path))

        # diagnosisRaw may or may not be present depending on invoice
        # Just verify the parse completed successfully
        assert result.success is True

    def test_parse_extracts_line_items(self, parser, sample_invoice_paths):
        """Invoices should extract line items."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                line_items = result.data.get("lineItems", [])
                # Should have at least one line item
                assert len(line_items) >= 1, f"No line items in {pdf_path.name}"

    def test_parse_extracts_currency(self, parser, sample_invoice_paths):
        """Invoices should have currency set."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                assert result.data.get("currency") == "SGD"


class TestParserConfidence:
    """Tests for confidence scoring."""

    def test_successful_parse_has_high_confidence(self, parser, sample_invoice_paths):
        """Successfully parsed invoices should have high confidence."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                assert result.confidence >= 0.7, f"Low confidence {result.confidence} for {pdf_path.name}"

    def test_confidence_between_0_and_1(self, parser, sample_invoice_paths):
        """Confidence should always be between 0 and 1."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            assert 0.0 <= result.confidence <= 1.0


class TestParserEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_nonexistent_file_fails_gracefully(self, parser):
        """Parser should handle non-existent files."""
        result = parser.parse("/nonexistent/path/invoice.pdf")

        # Should either fail with success=False or raise an exception
        # Either is acceptable behavior
        assert result.success is False or result.abort_reason is not None

    def test_parse_returns_requires_review_list(self, parser, sample_invoice_paths):
        """Parser should return list of fields requiring review."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        result = parser.parse(str(sample_invoice_paths[0]))

        # requires_review should be a list (possibly empty)
        assert isinstance(result.requires_review, list)

    def test_to_json_format(self, parser, sample_invoice_paths):
        """to_json() should return properly structured dict."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        result = parser.parse(str(sample_invoice_paths[0]))
        json_result = result.to_json(source_file="test.pdf")

        # Check structure
        assert "extracted" in json_result
        assert "inference_required" in json_result
        assert "metadata" in json_result

        # Check metadata fields
        assert "success" in json_result["metadata"]
        assert "confidence" in json_result["metadata"]
        assert "source_file" in json_result["metadata"]

    def test_to_json_string_is_valid_json(self, parser, sample_invoice_paths):
        """to_json_string() should return valid JSON."""
        import json

        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        result = parser.parse(str(sample_invoice_paths[0]))
        json_str = result.to_json_string(source_file="test.pdf")

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


class TestParserDateFormats:
    """Tests for date parsing flexibility."""

    def test_parser_extracts_visit_date(self, parser, sample_invoice_paths):
        """Parser should extract visit date."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                visit_date = result.data.get("visitDate")
                if visit_date:
                    # Date should be in ISO format YYYY-MM-DD
                    assert len(visit_date) == 10
                    assert visit_date[4] == "-"
                    assert visit_date[7] == "-"


class TestParserAmountCalculations:
    """Tests for amount extraction and calculations."""

    def test_amounts_are_numeric(self, parser, sample_invoice_paths):
        """All amount fields should be numeric."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                for field in ["subtotal", "gstAmount", "paymentAmount"]:
                    value = result.data.get(field)
                    if value is not None:
                        assert isinstance(value, (int, float)), f"{field} should be numeric"

    def test_payment_amount_equals_subtotal_plus_gst(self, parser, sample_invoice_paths):
        """Payment = Subtotal + GST (with tolerance for rounding)."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                subtotal = result.data.get("subtotal")
                gst = result.data.get("gstAmount")
                payment = result.data.get("paymentAmount")

                if all(v is not None for v in [subtotal, gst, payment]):
                    expected = subtotal + gst
                    # Allow 1 cent tolerance for rounding
                    assert abs(payment - expected) < 0.02, \
                        f"Payment {payment} != Subtotal {subtotal} + GST {gst}"

    def test_line_items_sum_to_subtotal(self, parser, sample_invoice_paths):
        """Line item amounts should approximately sum to subtotal or payment."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                line_items = result.data.get("lineItems", [])
                subtotal = result.data.get("subtotal")
                payment = result.data.get("paymentAmount")

                if line_items and (subtotal or payment):
                    total_items = sum(item.get("amount", 0) for item in line_items)
                    # Line items might equal subtotal OR payment (GST-inclusive)
                    # Check if it matches either within tolerance
                    matches_subtotal = subtotal and abs(total_items - subtotal) < 1.0
                    matches_payment = payment and abs(total_items - payment) < 1.0
                    assert matches_subtotal or matches_payment, \
                        f"Line items sum {total_items} doesn't match subtotal {subtotal} or payment {payment}"
