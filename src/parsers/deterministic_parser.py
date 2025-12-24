"""
Deterministic Parser for Bank Statements
Implements text-based extraction with defensive principles from TSD
"""

import pymupdf
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class ParserResult:
    """Result from deterministic parsing with confidence and warnings"""
    success: bool
    data: List[Dict]
    confidence: float
    warnings: List[str]
    abort_reason: Optional[str] = None


class DeterministicBankStatementParser:
    """
    Defensive parser for bank statement tables using PyMuPDF

    Implements:
    - Span merging (kerning correction)
    - Explicit abort semantics
    - Coordinate-based table extraction
    """

    def __init__(self):
        self.warnings = []
        self.confidence = 1.0

    def parse(self, pdf_path: str) -> ParserResult:
        """
        Main parsing entry point

        Args:
            pdf_path: Path to PDF bank statement

        Returns:
            ParserResult with extracted transactions or abort reason
        """
        try:
            doc = pymupdf.open(pdf_path)

            # Ingestion guard - check document integrity
            if not self._validate_document(doc):
                return ParserResult(
                    success=False,
                    data=[],
                    confidence=0.0,
                    warnings=self.warnings,
                    abort_reason="Document integrity check failed"
                )

            all_transactions = []

            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract transactions from this page
                transactions = self._extract_page_transactions(page, page_num)

                if transactions is None:
                    # Abort condition met
                    return ParserResult(
                        success=False,
                        data=[],
                        confidence=0.0,
                        warnings=self.warnings,
                        abort_reason=f"Failed to extract transactions from page {page_num + 1}"
                    )

                all_transactions.extend(transactions)

            doc.close()

            # Post-processing: merge balance carried forward entries
            cleaned_transactions = self._remove_balance_forward_entries(all_transactions)

            return ParserResult(
                success=True,
                data=cleaned_transactions,
                confidence=self.confidence,
                warnings=self.warnings
            )

        except Exception as e:
            return ParserResult(
                success=False,
                data=[],
                confidence=0.0,
                warnings=self.warnings + [str(e)],
                abort_reason=f"Unexpected error: {str(e)}"
            )

    def _validate_document(self, doc: pymupdf.Document) -> bool:
        """
        Ingestion guard - validate document integrity

        Implements TSD Section 4.1: Text layer integrity checks
        """
        if len(doc) == 0:
            self.warnings.append("Empty document")
            return False

        # Check for text layer on first page
        first_page = doc[0]
        text = first_page.get_text()

        if len(text.strip()) < 50:
            self.warnings.append("Insufficient text content - possible OCR needed")
            self.confidence *= 0.5

        # Check for expected headers (DBS/POSB specific)
        if "Transaction Details" not in text and "Account Summary" not in text:
            self.warnings.append("Expected headers not found")
            self.confidence *= 0.7

        return True

    def _extract_page_transactions(self, page: pymupdf.Page, page_num: int) -> Optional[List[Dict]]:
        """
        Extract transactions from a single page using text extraction with position info

        Returns:
            List of transaction dictionaries or None on abort
        """
        # Use PyMuPDF's words extraction - better for tabular data
        words = page.get_text("words")  # Returns list of (x0, y0, x1, y1, "word", block_no, line_no, word_no)

        if not words:
            self.warnings.append(f"No text found on page {page_num + 1}")
            return []

        # Group words by line (similar y-coordinate)
        lines = self._group_words_into_lines(words)

        # Find transaction table region
        table_start_idx = self._find_table_start_from_lines(lines)
        if table_start_idx is None:
            self.warnings.append(f"Could not find transaction table on page {page_num + 1}")
            return []  # Empty list, not abort - might be summary page

        # Extract transactions from table region
        transactions = self._parse_table_rows_from_lines(lines[table_start_idx:], page_num)

        return transactions

    def _group_words_into_lines(self, words: List[Tuple]) -> List[Dict]:
        """
        Group words into lines based on y-coordinate proximity

        Args:
            words: List of (x0, y0, x1, y1, "word", ...) tuples

        Returns:
            List of line dictionaries with words sorted by x position
        """
        if not words:
            return []

        # Group by similar y-coordinate (within 3 pixels)
        lines_dict = {}

        for word in words:
            x0, y0, x1, y1, text = word[:5]

            # Find existing line with similar y-coordinate
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

        # Convert to list and sort by y position
        lines = []
        for y_pos in sorted(lines_dict.keys()):
            # Sort words in line by x position
            words_in_line = sorted(lines_dict[y_pos], key=lambda w: w["x0"])
            lines.append({
                "y": y_pos,
                "words": words_in_line
            })

        return lines

    def _find_table_start_from_lines(self, lines: List[Dict]) -> Optional[int]:
        """
        Find the start of the transaction table from structured lines

        Looks for CURRENCY marker or first date pattern
        """
        for i, line in enumerate(lines):
            # Get all text in line
            line_text = " ".join([w["text"] for w in line["words"]])

            # Look for CURRENCY marker
            if "CURRENCY:" in line_text.upper():
                return i + 1

            # Or look for first transaction date pattern
            if re.match(r'^\d{2}/\d{2}/\d{4}', line_text.strip()):
                # This is first transaction
                return i

        return None

    def _parse_table_rows_from_lines(self, lines: List[Dict], page_num: int) -> List[Dict]:
        """
        Parse table rows from structured lines with position information

        Uses column positions to separate Date, Description, and amounts
        """
        transactions = []
        current_transaction = None

        for line in lines:
            # Get all text to check for markers
            line_text = " ".join([w["text"] for w in line["words"]])

            # Check for end of table markers
            if any(marker in line_text for marker in [
                "Balance Carried Forward",
                "Total Balance Carried Forward",
                "Messages For",
                "Transaction Details as of",
                "Page"
            ]):
                # End of table on this page
                if current_transaction:
                    transactions.append(current_transaction)
                break

            # Try to parse as transaction using column positions
            parsed = self._parse_transaction_from_words(line["words"])

            if parsed and parsed.get("date"):
                # This is a new transaction
                if current_transaction:
                    transactions.append(current_transaction)
                current_transaction = parsed
                current_transaction["page"] = page_num + 1
            elif current_transaction and line["words"]:
                # This might be a continuation line
                # Check if it contains amounts we should add to the transaction
                has_amount = False
                for word in line["words"]:
                    text = word["text"]
                    x_pos = word["x0"]
                    amount = self._try_parse_amount(text)

                    if amount is not None:
                        has_amount = True
                        # Classify based on x-coordinate column
                        if x_pos > 503:
                            # Balance column
                            if not current_transaction["balance"]:
                                current_transaction["balance"] = amount
                        elif x_pos > 440:
                            # Deposit column
                            if not current_transaction["deposit"]:
                                current_transaction["deposit"] = amount
                        elif x_pos > 364:
                            # Withdrawal column
                            if not current_transaction["withdrawal"]:
                                current_transaction["withdrawal"] = amount

                # If no amounts found, add as description text
                if not has_amount:
                    continuation_text = " ".join([w["text"] for w in line["words"]])
                    current_transaction["description"] += " " + continuation_text

        # Add final transaction
        if current_transaction:
            transactions.append(current_transaction)

        return transactions

    def _parse_transaction_from_words(self, words: List[Dict]) -> Optional[Dict]:
        """
        Parse transaction from positioned words using x-coordinate columns

        Based on diagnostic analysis of actual PDF coordinates:
        - Date: x < 55
        - Description: 103 < x < 364
        - Withdrawal column: 364 < x < 440
        - Deposit column: 440 < x < 503
        - Balance column: x > 503
        """
        if not words:
            return None

        # Check if first word is a date
        first_word = words[0]["text"]
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', first_word):
            return None

        date = first_word
        description_parts = []
        withdrawal = None
        deposit = None
        balance = None

        # Process remaining words and classify by x-coordinate
        for word in words[1:]:  # Skip date
            text = word["text"]
            x_pos = word["x0"]

            # Try to parse as amount
            amount = self._try_parse_amount(text)

            if amount is not None:
                # Classify based on x-coordinate column
                if x_pos > 503:
                    # Balance column (rightmost)
                    balance = amount
                elif x_pos > 440:
                    # Deposit column (middle-right)
                    deposit = amount
                elif x_pos > 364:
                    # Withdrawal column (middle-left)
                    withdrawal = amount
                else:
                    # Amount appears in description area - shouldn't happen
                    # Treat as description text
                    description_parts.append(text)
            else:
                # This is description text (x should be between 103-364)
                description_parts.append(text)

        description = " ".join(description_parts).strip()

        # Validation: If we have withdrawal but no balance, and amount > 1000,
        # it's probably misclassified (should be balance)
        if withdrawal and not balance and withdrawal > 1000:
            balance = withdrawal
            withdrawal = None

        # If we have deposit but no balance, and amount > 1000,
        # it's probably misclassified (should be balance)
        if deposit and not balance and deposit > 1000:
            balance = deposit
            deposit = None

        return {
            "date": date,
            "description": description,
            "withdrawal": withdrawal,
            "deposit": deposit,
            "balance": balance
        }

    def _try_parse_amount(self, text: str) -> Optional[float]:
        """Try to parse text as a monetary amount"""
        # Remove any non-numeric characters except comma and period
        cleaned = re.sub(r'[^\d,\.]', '', text)

        # Check if it looks like an amount (has decimal point)
        if '.' in cleaned and re.match(r'^[\d,]+\.\d{2}$', cleaned):
            return self._parse_amount(cleaned)

        return None

    def _parse_transaction_line(self, text: str) -> Optional[Dict]:
        """
        Parse a single transaction line

        Expected format: DD/MM/YYYY Description Amount Amount Balance
        """
        # Date pattern at start of line
        date_pattern = r'^(\d{2}/\d{2}/\d{4})'
        date_match = re.match(date_pattern, text)

        if not date_match:
            return None

        date_str = date_match.group(1)
        remaining = text[len(date_str):].strip()

        # Extract amounts from end of line (right-aligned)
        # Pattern: optional withdrawal, optional deposit, balance (all decimal numbers)
        amount_pattern = r'([\d,]+\.\d{2})'
        amounts = re.findall(amount_pattern, remaining)

        # Determine which amounts are which based on count
        withdrawal = None
        deposit = None
        balance = None

        if len(amounts) >= 1:
            balance = self._parse_amount(amounts[-1])

        if len(amounts) >= 2:
            # Could be withdrawal + balance or deposit + balance
            # Need to extract description to determine
            # For now, assume single amount before balance
            amount_before_balance = self._parse_amount(amounts[-2])
            # We'll determine if it's withdrawal or deposit from description context

        if len(amounts) >= 3:
            withdrawal = self._parse_amount(amounts[-3])
            deposit = self._parse_amount(amounts[-2])

        # Extract description (everything between date and amounts)
        # Remove all amount strings from remaining text
        description = remaining
        for amt_str in amounts:
            description = description.replace(amt_str, "")
        description = description.strip()

        # Determine withdrawal vs deposit based on description
        if len(amounts) == 2 and amount_before_balance:
            if any(keyword in description.upper() for keyword in [
                "WITHDRAWAL", "PAYMENT", "TRANSFER TO", "ATM", "DEBIT"
            ]):
                withdrawal = amount_before_balance
            elif any(keyword in description.upper() for keyword in [
                "DEPOSIT", "INCOMING", "RECEIPT", "FROM:", "SALARY", "CREDIT"
            ]):
                deposit = amount_before_balance

        return {
            "date": date_str,
            "description": description,
            "withdrawal": withdrawal,
            "deposit": deposit,
            "balance": balance
        }

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float, handling commas"""
        try:
            # Remove commas and convert
            clean_str = amount_str.replace(",", "")
            return float(clean_str)
        except (ValueError, AttributeError):
            return None

    def _remove_balance_forward_entries(self, transactions: List[Dict]) -> List[Dict]:
        """
        Remove 'Balance Brought Forward' and 'Balance Carried Forward' entries
        These are pagination artifacts, not real transactions
        """
        return [
            t for t in transactions
            if "Balance Brought Forward" not in t.get("description", "")
            and "Balance Carried Forward" not in t.get("description", "")
        ]


def main():
    """Example usage"""
    import json

    parser = DeterministicBankStatementParser()
    result = parser.parse("resources/statements/702490847-DBS-Singapore-Bank-Statement-pdf.pdf")

    if result.success:
        print(f"[SUCCESS] Extraction successful!")
        print(f"  Confidence: {result.confidence:.2%}")
        print(f"  Transactions extracted: {len(result.data)}")
        print(f"  Warnings: {len(result.warnings)}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        print("\nFirst 10 transactions:")
        for i, txn in enumerate(result.data[:10], 1):
            print(f"\n{i}. {txn['date']} - Page {txn['page']}")
            print(f"   Description: {txn['description'][:80]}")
            if len(txn['description']) > 80:
                print(f"                {txn['description'][80:160]}")
            print(f"   Withdrawal: {f'SGD {txn["withdrawal"]:.2f}' if txn['withdrawal'] else '-':>15}")
            print(f"   Deposit:    {f'SGD {txn["deposit"]:.2f}' if txn['deposit'] else '-':>15}")
            print(f"   Balance:    {f'SGD {txn["balance"]:.2f}' if txn['balance'] else '-':>15}")

        # Save to JSON
        output_path = "extracted_data.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "success": result.success,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "transaction_count": len(result.data),
                "transactions": result.data
            }, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] Data exported to {output_path}")

        # Summary statistics
        total_withdrawals = sum(t['withdrawal'] for t in result.data if t['withdrawal'])
        total_deposits = sum(t['deposit'] for t in result.data if t['deposit'])
        print(f"\nSummary Statistics:")
        print(f"  Total Withdrawals: SGD {total_withdrawals:,.2f}")
        print(f"  Total Deposits:    SGD {total_deposits:,.2f}")
        print(f"  Net Change:        SGD {total_deposits - total_withdrawals:,.2f}")

        if result.data:
            first_balance = result.data[0]['balance']
            last_balance = result.data[-1]['balance']
            print(f"  First Balance:     SGD {first_balance:,.2f}")
            print(f"  Last Balance:      SGD {last_balance:,.2f}")
            print(f"  Calculated Change: SGD {last_balance - first_balance:,.2f}")
    else:
        print(f"[FAILED] Extraction failed")
        print(f"  Reason: {result.abort_reason}")
        print(f"  Warnings: {result.warnings}")


if __name__ == "__main__":
    main()
