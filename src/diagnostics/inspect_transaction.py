"""
Inspect specific transactions in detail to understand multi-line structure
"""

import pymupdf
from collections import defaultdict

def inspect_transaction_area(pdf_path: str, page_num: int = 1, y_range: tuple = (240, 350)):
    """
    Inspect all words in a specific area of the PDF

    Args:
        pdf_path: Path to PDF
        page_num: Page number (0-indexed)
        y_range: (min_y, max_y) to inspect
    """
    doc = pymupdf.open(pdf_path)
    page = doc[page_num]
    words = page.get_text("words")

    print(f"Inspecting page {page_num + 1}, Y range {y_range[0]}-{y_range[1]}")
    print("=" * 100)

    # Group by y-coordinate
    lines_dict = defaultdict(list)
    for word in words:
        x0, y0, x1, y1, text = word[:5]
        if y_range[0] <= y0 <= y_range[1]:
            line_key = round(y0 / 3) * 3
            lines_dict[line_key].append({
                "text": text,
                "x0": x0,
                "y0": y0
            })

    # Print each line
    for y_pos in sorted(lines_dict.keys()):
        words_in_line = sorted(lines_dict[y_pos], key=lambda w: w["x0"])
        print(f"\nY={y_pos:.1f}")
        for word in words_in_line:
            print(f"  X={word['x0']:6.1f}: {word['text']}")

    doc.close()

if __name__ == "__main__":
    # Inspect first two transactions on page 2
    inspect_transaction_area(
        "resources/statements/702490847-DBS-Singapore-Bank-Statement-pdf.pdf",
        page_num=1,
        y_range=(240, 350)
    )
