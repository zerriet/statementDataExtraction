"""
Diagnostic tool to analyze actual x-coordinates in bank statement PDF

This helps us understand the real column positions for accurate parsing.
"""

import pymupdf
import re
from collections import defaultdict


def analyze_coordinates(pdf_path: str, max_pages: int = 3):
    """
    Analyze x-coordinates of different text elements in the PDF

    Args:
        pdf_path: Path to PDF file
        max_pages: Number of pages to analyze (default: 3)
    """
    doc = pymupdf.open(pdf_path)

    print("=" * 100)
    print("PDF COORDINATE ANALYSIS - Understanding Column Positions")
    print("=" * 100)
    print(f"\nAnalyzing first {max_pages} transaction pages...\n")

    # Collect data
    date_positions = []
    amount_positions = []  # (x_pos, amount, line_y)
    description_positions = []

    pages_analyzed = 0

    for page_num in range(len(doc)):
        if pages_analyzed >= max_pages:
            break

        page = doc[page_num]
        words = page.get_text("words")

        # Group words by line
        lines_dict = defaultdict(list)
        for word in words:
            x0, y0, x1, y1, text = word[:5]
            # Group by y-coordinate (within 3 pixels)
            line_key = round(y0 / 3) * 3
            lines_dict[line_key].append({
                "text": text,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1
            })

        # Process lines
        for y_pos in sorted(lines_dict.keys()):
            words_in_line = sorted(lines_dict[y_pos], key=lambda w: w["x0"])
            line_text = " ".join([w["text"] for w in words_in_line])

            # Check if this is a transaction line
            if re.match(r'^\d{2}/\d{2}/\d{4}', line_text.strip()):
                pages_analyzed += 1 if pages_analyzed == 0 else 0

                print(f"\n[Page {page_num + 1}, Y={y_pos:.1f}] Transaction Line:")
                print(f"  Full Text: {line_text[:100]}...")
                print(f"  Words and X-positions:")

                for word in words_in_line:
                    print(f"    x={word['x0']:6.1f} - {word['text']}")

                    # Categorize
                    if re.match(r'^\d{2}/\d{2}/\d{4}$', word['text']):
                        date_positions.append(word['x0'])
                    elif re.match(r'^[\d,]+\.\d{2}$', word['text']):
                        # This is an amount
                        amount = float(word['text'].replace(',', ''))
                        amount_positions.append((word['x0'], amount, y_pos))
                    elif len(word['text']) > 2 and not re.match(r'^[\d,\.]+$', word['text']):
                        # This is description text
                        description_positions.append(word['x0'])

        if pages_analyzed >= max_pages:
            break

    doc.close()

    # Analyze collected data
    print("\n" + "=" * 100)
    print("ANALYSIS SUMMARY")
    print("=" * 100)

    # Date column
    if date_positions:
        print(f"\nDate Column (n={len(date_positions)}):")
        print(f"  X-position range: {min(date_positions):.1f} - {max(date_positions):.1f}")
        print(f"  Average: {sum(date_positions)/len(date_positions):.1f}")

    # Description column
    if description_positions:
        print(f"\nDescription Column (n={len(description_positions)}):")
        print(f"  X-position range: {min(description_positions):.1f} - {max(description_positions):.1f}")
        print(f"  Average: {sum(description_positions)/len(description_positions):.1f}")

    # Amount columns - this is the key insight!
    if amount_positions:
        print(f"\nAmount Positions (n={len(amount_positions)}):")

        # Group by x-position clusters
        amount_positions.sort(key=lambda x: x[0])

        # Find clusters (amounts within 50 pixels are same column)
        clusters = []
        current_cluster = [amount_positions[0]]

        for i in range(1, len(amount_positions)):
            if amount_positions[i][0] - current_cluster[-1][0] < 50:
                current_cluster.append(amount_positions[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [amount_positions[i]]
        clusters.append(current_cluster)

        print(f"\n  Found {len(clusters)} distinct column(s):")
        for i, cluster in enumerate(clusters, 1):
            x_positions = [pos[0] for pos in cluster]
            amounts = [pos[1] for pos in cluster]
            print(f"\n  Column {i}:")
            print(f"    X-position range: {min(x_positions):.1f} - {max(x_positions):.1f}")
            print(f"    Average X: {sum(x_positions)/len(x_positions):.1f}")
            print(f"    Sample count: {len(cluster)}")
            print(f"    Sample amounts: {amounts[:5]}")

    # Recommend column boundaries
    print("\n" + "=" * 100)
    print("RECOMMENDED COLUMN BOUNDARIES")
    print("=" * 100)

    if date_positions and description_positions and amount_positions:
        date_max = max(date_positions)
        desc_min = min(description_positions)

        # Analyze amount clusters more carefully
        if len(clusters) >= 3:
            # We have all three columns visible
            withdrawal_x = sum([pos[0] for pos in clusters[0]]) / len(clusters[0])
            deposit_x = sum([pos[0] for pos in clusters[1]]) / len(clusters[1])
            balance_x = sum([pos[0] for pos in clusters[2]]) / len(clusters[2])

            print(f"""
Detected 3 amount columns (Withdrawal, Deposit, Balance):

  Date:        x < {date_max + 10:.1f}
  Description: {desc_min - 10:.1f} < x < {withdrawal_x - 10:.1f}
  Withdrawal:  {withdrawal_x - 10:.1f} < x < {deposit_x - 10:.1f}
  Deposit:     {deposit_x - 10:.1f} < x < {balance_x - 10:.1f}
  Balance:     x > {balance_x - 10:.1f}
            """)

        elif len(clusters) == 2:
            first_x = sum([pos[0] for pos in clusters[0]]) / len(clusters[0])
            balance_x = sum([pos[0] for pos in clusters[1]]) / len(clusters[1])

            print(f"""
Detected 2 amount columns (Amount + Balance):

  Date:        x < {date_max + 10:.1f}
  Description: {desc_min - 10:.1f} < x < {first_x - 10:.1f}
  Amount:      {first_x - 10:.1f} < x < {balance_x - 10:.1f}  (Withdrawal OR Deposit - needs keyword detection)
  Balance:     x > {balance_x - 10:.1f}
            """)
        else:
            balance_x = sum([pos[0] for pos in clusters[0]]) / len(clusters[0])

            print(f"""
Detected 1 amount column (Balance only):

  Date:        x < {date_max + 10:.1f}
  Description: {desc_min - 10:.1f} < x < {balance_x - 10:.1f}
  Balance:     x > {balance_x - 10:.1f}
            """)

    print("\n" + "=" * 100)


if __name__ == "__main__":
    analyze_coordinates("resources/statements/702490847-DBS-Singapore-Bank-Statement-pdf.pdf", max_pages=2)
