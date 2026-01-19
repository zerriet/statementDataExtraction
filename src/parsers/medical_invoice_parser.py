"""
Medical Invoice Parser
Implements text-based extraction for medical invoices with defensive principles from TSD

Supports multiple invoice formats:
- City Osteopathy style (structured table with ITEM/QTY/PRICE/ADJ/SUBTOTAL)
- OneDoctors style (Item Name/Quantity/UOM/DISC/Total Price)
"""

import pymupdf
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
import json


@dataclass
class MedicalInvoiceResult:
    """Result from medical invoice parsing with confidence and warnings"""
    success: bool
    data: Dict
    confidence: float
    warnings: List[str]
    requires_review: List[str] = field(default_factory=list)  # Fields needing HITL
    abort_reason: Optional[str] = None

    def to_json(self, source_file: str = None) -> Dict:
        """
        Export result as JSON-serializable dict for upstream framework.

        Returns:
            Dict with 'extracted', 'inference_required', and 'metadata' keys
        """
        return {
            "extracted": self.data,
            "inference_required": self.requires_review,
            "metadata": {
                "success": self.success,
                "confidence": self.confidence,
                "warnings": self.warnings,
                "source_file": source_file,
                "abort_reason": self.abort_reason
            }
        }

    def to_json_string(self, source_file: str = None, indent: int = 2) -> str:
        """Export result as formatted JSON string"""
        return json.dumps(self.to_json(source_file), indent=indent, ensure_ascii=False)


class MedicalInvoiceParser:
    """
    Defensive parser for medical invoices using PyMuPDF

    Extracts fields that can be directly parsed from invoice PDFs.
    Fields requiring inference (benefitType, diagnosisCode) are flagged for review.
    """

    # Date patterns to handle multiple formats
    DATE_PATTERNS = [
        (r'(\d{1,2}\s+\w{3}\s+\d{4})', '%d %b %Y'),      # 10 Jan 2026
        (r'(\d{2}-\d{2}-\d{4})', '%d-%m-%Y'),             # 19-04-2025
        (r'(\d{2}/\d{2}/\d{4})', '%d/%m/%Y'),             # 10/01/2026
        (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),             # 2026-01-10
    ]

    def __init__(self):
        self.warnings = []
        self.confidence = 1.0
        self.requires_review = []

    def parse(self, pdf_path: str) -> MedicalInvoiceResult:
        """
        Main parsing entry point

        Args:
            pdf_path: Path to medical invoice PDF

        Returns:
            MedicalInvoiceResult with extracted data or abort reason
        """
        # Reset state for each parse call to prevent leakage between invocations
        self.warnings = []
        self.confidence = 1.0
        self.requires_review = []

        try:
            doc = pymupdf.open(pdf_path)

            if not self._validate_document(doc):
                return MedicalInvoiceResult(
                    success=False,
                    data={},
                    confidence=0.0,
                    warnings=self.warnings,
                    abort_reason="Document integrity check failed"
                )

            # Extract all text and words from first page (invoices are typically single page)
            page = doc[0]
            text = page.get_text()
            words = page.get_text("words")
            lines = self._group_words_into_lines(words)

            # Extract invoice data
            invoice_data = self._extract_invoice_data(text, lines)

            doc.close()

            return MedicalInvoiceResult(
                success=True,
                data=invoice_data,
                confidence=self.confidence,
                warnings=self.warnings,
                requires_review=self.requires_review
            )

        except Exception as e:
            return MedicalInvoiceResult(
                success=False,
                data={},
                confidence=0.0,
                warnings=self.warnings + [str(e)],
                abort_reason=f"Unexpected error: {str(e)}"
            )

    def _validate_document(self, doc: pymupdf.Document) -> bool:
        """Ingestion guard - validate document integrity"""
        if len(doc) == 0:
            self.warnings.append("Empty document")
            return False

        first_page = doc[0]
        text = first_page.get_text()

        if len(text.strip()) < 50:
            self.warnings.append("Insufficient text content - possible OCR needed")
            self.confidence *= 0.5

        # Check for invoice indicators
        invoice_indicators = ["invoice", "tax invoice", "receipt", "total", "amount"]
        text_lower = text.lower()
        if not any(ind in text_lower for ind in invoice_indicators):
            self.warnings.append("Document may not be an invoice")
            self.confidence *= 0.7

        return True

    def _group_words_into_lines(self, words: List[Tuple]) -> List[Dict]:
        """Group words into lines based on y-coordinate proximity"""
        if not words:
            return []

        lines_dict = {}

        for word in words:
            x0, y0, x1, y1, text = word[:5]

            line_key = None
            for existing_y in lines_dict.keys():
                if abs(existing_y - y0) < 3:
                    line_key = existing_y
                    break

            if line_key is None:
                line_key = y0
                lines_dict[line_key] = []

            lines_dict[line_key].append({
                "text": text,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1
            })

        lines = []
        for y_pos in sorted(lines_dict.keys()):
            words_in_line = sorted(lines_dict[y_pos], key=lambda w: w["x0"])
            lines.append({
                "y": y_pos,
                "words": words_in_line,
                "text": " ".join([w["text"] for w in words_in_line])
            })

        return lines

    def _extract_invoice_data(self, text: str, lines: List[Dict]) -> Dict:
        """Extract all invoice fields from text and structured lines"""

        data = {
            "invoiceNumber": self._extract_invoice_number(text),
            "visitDate": self._extract_date(text, lines),
            "providerName": self._extract_provider_name(lines),
            "patientName": self._extract_patient_name(text, lines),
            "lineItems": self._extract_line_items(lines),
            "subtotal": None,
            "gstAmount": None,
            "paymentAmount": None,
            "currency": "SGD",
            "diagnosisRaw": self._extract_diagnosis_raw(text),
        }

        # Extract amounts
        amounts = self._extract_amounts(text)
        data["subtotal"] = amounts.get("subtotal")
        data["gstAmount"] = amounts.get("gst")
        data["paymentAmount"] = amounts.get("total")

        # Calculate subtotal if not found but we have total and GST
        if data["subtotal"] is None and data["paymentAmount"] and data["gstAmount"]:
            data["subtotal"] = round(data["paymentAmount"] - data["gstAmount"], 2)
            self.warnings.append("Subtotal calculated from total - gstAmount")

        # Flag fields requiring inference
        self._flag_inference_fields(data)

        return data

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice number from various formats"""
        patterns = [
            r'Tax\s+Invoice\s*#[:\s]*([A-Z0-9-]+)',      # Tax Invoice #: INV-2601000859
            r'Invoice\s+No\.?\s*[:\s]*([A-Z0-9-]+)',     # Invoice No. H101494
            r'Invoice\s*#[:\s]*([A-Z0-9-]+)',            # Invoice #: XXX
            r'Receipt\s+No\.?\s*[:\s]*([A-Z0-9-]+)',     # Receipt No. XXX
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        self.warnings.append("Could not extract invoice number")
        return None

    def _extract_date(self, text: str, lines: List[Dict]) -> Optional[str]:
        """Extract and normalize invoice date to YYYY-MM-DD format"""
        # Look for date labels
        date_labels = [
            r'Issued\s+on[:\s]*',
            r'Invoice\s+Date\s*[:\s]*',
            r'Date[:\s]*',
        ]

        for label in date_labels:
            for pattern, date_format in self.DATE_PATTERNS:
                full_pattern = label + pattern
                match = re.search(full_pattern, text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(1)
                        parsed_date = datetime.strptime(date_str, date_format)
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        continue

        # Fallback: look for any date pattern in text
        for pattern, date_format in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(1)
                    parsed_date = datetime.strptime(date_str, date_format)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue

        self.warnings.append("Could not extract visit date")
        return None

    def _extract_provider_name(self, lines: List[Dict]) -> Optional[str]:
        """Extract provider/clinic name (typically first lines of document)"""
        if not lines:
            return None

        # Provider name is usually in first 1-3 lines, before address/registration
        # Skip lines that look like addresses or registration numbers
        skip_patterns = [
            r'^\d+\s',           # Starts with number (address)
            r'^#\d+',            # Unit number
            r'Singapore\s+\d+',  # Singapore postal
            r'^\d{9}[A-Z]$',     # UEN/registration number
            r'^Tel\s*:',         # Phone
            r'^ACRA',            # Registration
            r'^GST',             # GST number
        ]

        provider_parts = []
        for line in lines[:5]:  # Check first 5 lines
            line_text = line["text"].strip()

            if not line_text:
                continue

            # Check if this looks like provider name (not address/reg)
            is_skip = any(re.match(p, line_text, re.IGNORECASE) for p in skip_patterns)

            if not is_skip and len(line_text) > 3:
                # Could be provider name
                if not provider_parts:
                    provider_parts.append(line_text)
                    break  # Usually just first line is the name

        if provider_parts:
            return " ".join(provider_parts)

        self.warnings.append("Could not extract provider name")
        return None

    def _extract_patient_name(self, text: str, lines: List[Dict]) -> Optional[str]:
        """Extract patient name"""
        # Look for Patient: label
        patterns = [
            r'Patient[:\s]+([A-Z][A-Za-z\s]+?)(?:\s*\([^)]+\))?(?:\n|$)',  # Patient: Name (ID)
            r'^([A-Z][A-Z\s]+)(?:\s+Ref\s+ID|\s+NRIC)',  # NAME Ref ID or NAME NRIC
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Clean up - remove extra whitespace
                name = " ".join(name.split())
                if len(name) > 3:
                    return name

        # Fallback: look for a line that's all caps (common for patient names)
        for line in lines:
            line_text = line["text"].strip()
            # Check if it's a name (all caps, 2-4 words, no numbers)
            if (line_text.isupper() and
                not any(c.isdigit() for c in line_text) and
                2 <= len(line_text.split()) <= 5 and
                10 < len(line_text) < 50):
                # Additional check: not a header
                if not any(kw in line_text for kw in ["ITEM", "INVOICE", "TOTAL", "RECEIPT", "QTY"]):
                    return line_text

        self.warnings.append("Could not extract patient name")
        return None

    def _extract_line_items(self, lines: List[Dict]) -> List[Dict]:
        """Extract itemized line items from invoice table"""
        items = []

        # Find table header to identify table region
        table_start = None
        table_end = None

        header_patterns = ["ITEM", "Item Name", "Description"]
        end_patterns = ["SUBTOTAL", "TOTAL", "GST", "Amount Paid", "Balance"]

        for i, line in enumerate(lines):
            line_text = line["text"].upper()

            if table_start is None:
                if any(hp.upper() in line_text for hp in header_patterns):
                    table_start = i + 1
            elif table_end is None:
                if any(ep.upper() in line_text for ep in end_patterns):
                    table_end = i
                    break

        if table_start is None:
            return items

        if table_end is None:
            table_end = len(lines)

        # Parse items between header and totals
        for line in lines[table_start:table_end]:
            line_text = line["text"].strip()

            # Skip empty lines or lines that are just numbers
            if not line_text or re.match(r'^[\d\s\.\$,]+$', line_text):
                continue

            # Skip lines that look like subtotals/totals
            if any(kw in line_text.upper() for kw in ["SUBTOTAL", "TOTAL", "GST", "PAID", "BALANCE"]):
                continue

            # Try to extract item with price
            item = self._parse_line_item(line_text)
            if item:
                items.append(item)

        return items

    def _parse_line_item(self, line_text: str) -> Optional[Dict]:
        """Parse a single line item"""
        # Look for price at end of line (last occurrence of amount pattern)
        price_matches = list(re.finditer(r'(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})', line_text))

        if price_matches:
            # Take the last amount as the line total
            last_match = price_matches[-1]
            price = self._parse_amount(last_match.group(1))

            # Description is everything before the first amount
            first_match = price_matches[0]
            description = line_text[:first_match.start()].strip()

            # Clean up description - remove quantity/unit info
            description = re.sub(r'\s+\d+\s+(EA|ml|Tablet|Bottle|pcs)\s*', ' ', description, flags=re.IGNORECASE)
            description = re.sub(r'\s+-?\d+%\s*', ' ', description)  # Remove discount %
            description = re.sub(r'\s+\d+\s*$', '', description)  # Remove trailing quantity
            description = ' '.join(description.split())  # Normalize whitespace

            if description and price is not None:
                return {
                    "description": description.strip(),
                    "amount": price
                }

        return None

    def _extract_amounts(self, text: str) -> Dict[str, Optional[float]]:
        """Extract subtotal, GST, and total amounts"""
        amounts = {
            "subtotal": None,
            "gst": None,
            "total": None
        }

        # Subtotal patterns
        subtotal_patterns = [
            r'SUBTOTAL[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',
            r'Sub\s*Total[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',
        ]
        for pattern in subtotal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amounts["subtotal"] = self._parse_amount(match.group(1))
                break

        # GST patterns
        gst_patterns = [
            r'GST\s*\([^)]*\)[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',  # GST (9%): SGD 15.30
            r'Inclusive\s+of\s+GST[^:]*[:\s]*\$?\s*([\d,]+\.\d{2})',   # Inclusive of GST 9%: $3.78
            r'GST[:\s]*(?:SGD\s*)?\$?\s*([\d,]+\.\d{2})',              # GST: SGD 15.30
        ]
        for pattern in gst_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amounts["gst"] = self._parse_amount(match.group(1))
                break

        # Total patterns (be careful not to match subtotal)
        total_patterns = [
            r'(?<!SUB)TOTAL[:\s]*\$?\s*SGD\s*([\d,]+\.\d{2})',  # TOTAL: SGD 185.30
            r'(?<!SUB)TOTAL[:\s]*\$?\s*([\d,]+\.\d{2})',        # Total: $45.78
            r'Amount\s+Paid[:\s]*\$?\s*([\d,]+\.\d{2})',        # Amount Paid: $45.78
            r'PAID[:\s]*\$?\s*SGD\s*([\d,]+\.\d{2})',           # PAID: SGD 185.30
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amounts["total"] = self._parse_amount(match.group(1))
                break

        return amounts

    def _extract_diagnosis_raw(self, text: str) -> Optional[str]:
        """Extract raw diagnosis text if present (for inference layer)"""
        patterns = [
            r'Diagnosis\s*[:\s]+([^\n]+)',
            r'Remark\s*[:\s]+Diagnosis\s*[:\s]+([^\n]+)',
            r'Condition\s*[:\s]+([^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                diagnosis = match.group(1).strip()
                # Clean up
                diagnosis = re.sub(r'^[:\s]+', '', diagnosis)
                if diagnosis:
                    return diagnosis

        return None

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float"""
        try:
            clean_str = amount_str.replace(",", "").replace("$", "").strip()
            return float(clean_str)
        except (ValueError, AttributeError):
            return None

    def _flag_inference_fields(self, data: Dict):
        """Flag fields that require inference/HITL review"""
        # Diagnosis requires mapping from raw text to code
        if data.get("diagnosisRaw"):
            self.requires_review.append("diagnosisCode: raw text found, needs mapping")
        else:
            self.requires_review.append("diagnosisCode: no diagnosis found in invoice")
            self.confidence *= 0.9

        # Benefit type requires inference from provider name
        self.requires_review.append("benefitType: requires inference from provider name")

        # Benefit category requires inference
        self.requires_review.append("benefitCategory: requires inference")


def parse_invoice(pdf_path: str) -> Dict:
    """
    Convenience function for single invoice parsing.
    Returns JSON-serializable dict for upstream framework.

    Args:
        pdf_path: Path to medical invoice PDF

    Returns:
        Dict with 'extracted', 'inference_required', and 'metadata' keys
    """
    from pathlib import Path
    parser = MedicalInvoiceParser()
    result = parser.parse(pdf_path)
    return result.to_json(source_file=Path(pdf_path).name)


def parse_invoice_folder(folder_path: str) -> List[Dict]:
    """
    Parse all PDF invoices in a folder.

    Args:
        folder_path: Path to folder containing invoice PDFs

    Returns:
        List of JSON-serializable dicts for upstream framework
    """
    from pathlib import Path
    folder = Path(folder_path)
    results = []

    for pdf_path in sorted(folder.glob("*.pdf")):
        parser = MedicalInvoiceParser()
        result = parser.parse(str(pdf_path))
        results.append(result.to_json(source_file=pdf_path.name))

    return results


def main():
    """Example usage demonstrating JSON output for upstream framework"""
    import sys
    from pathlib import Path

    print("=" * 60)
    print("Medical Invoice Parser - Demo")
    print("=" * 60)

    # Test with invoice files
    test_files = [
        "resources/statements/medical_invoice_statements/invoice1.pdf",
        "resources/statements/medical_invoice_statements/invoice2.pdf",
    ]

    all_results = []

    for pdf_path in test_files:
        print(f"\nParsing: {Path(pdf_path).name}")
        print("-" * 40)

        # Use convenience function
        output = parse_invoice(pdf_path)
        all_results.append(output)

        # Display summary
        extracted = output['extracted']
        metadata = output['metadata']

        print(f"Status: {'SUCCESS' if metadata['success'] else 'FAILED'}")
        print(f"Confidence: {metadata['confidence']:.0%}")
        print(f"Invoice #: {extracted.get('invoiceNumber')}")
        print(f"Total: {extracted.get('currency')} {extracted.get('paymentAmount')}")
        print(f"Diagnosis: {extracted.get('diagnosisRaw') or '(not found - needs HITL)'}")

    # Output JSON for upstream framework
    print("\n" + "=" * 60)
    print("JSON Output for Upstream Agentic Framework:")
    print("=" * 60)
    print(json.dumps(all_results, indent=2, ensure_ascii=False))

    # Save to file
    output_path = Path("extracted_data/medical_invoices_extracted.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
