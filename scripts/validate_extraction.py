"""
Validation script to compare extracted data against known PDF values
"""

import json

# Load extracted data
with open('extracted_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

transactions = data.get('data') or data.get('transactions', [])

print("=" * 100)
print("VALIDATION REPORT: Comparing Extracted Data vs PDF")
print("=" * 100)
print(f"\nTotal Transactions Extracted: {len(transactions)}")
print(f"Confidence: {data['confidence']:.2%}")
print(f"Warnings: {len(data['warnings'])}")

# Known transactions from PDF (Page 2) for validation
expected_page_2 = [
    {
        "date": "01/01/2022",
        "description": "Debit Card Transaction 7-ELEVEN",
        "withdrawal": 20.00,
        "deposit": None,
        "balance": 7980.00
    },
    {
        "date": "01/01/2022",
        "description": "INCOMING PAYNOW",
        "withdrawal": 4.40,
        "deposit": 20.00,
        "balance": 7975.60
    },
    {
        "date": "02/01/2022",
        "description": "Point-of-Sale Transaction.*DHEEN",
        "withdrawal": 5.00,
        "deposit": None,
        "balance": 7970.60
    },
    {
        "date": "02/12/2022",
        "description": "Debit Card Transaction 7-ELEVEN",
        "withdrawal": 2.20,
        "deposit": None,
        "balance": 7968.40
    },
    {
        "date": "02/01/2022",
        "description": "INCOMING PAYNOW.*RAM PREET",
        "withdrawal": None,
        "deposit": 125.00,
        "balance": 8093.40
    }
]

print("\n" + "=" * 100)
print("SAMPLE VALIDATION (First 5 transactions from Page 2)")
print("=" * 100)

for i, (extracted, expected) in enumerate(zip(transactions[:5], expected_page_2), 1):
    print(f"\n[Transaction {i}] {extracted['date']}")
    print(f"  Description: {extracted['description'][:60]}...")

    # Compare withdrawal
    match_w = "OK" if extracted['withdrawal'] == expected['withdrawal'] else "MISMATCH"
    print(f"  Withdrawal: Expected={expected['withdrawal']}, Got={extracted['withdrawal']} [{match_w}]")

    # Compare deposit
    match_d = "OK" if extracted['deposit'] == expected['deposit'] else "MISMATCH"
    print(f"  Deposit:    Expected={expected['deposit']}, Got={extracted['deposit']} [{match_d}]")

    # Compare balance
    match_b = "OK" if abs((extracted['balance'] or 0) - (expected['balance'] or 0)) < 0.01 else "MISMATCH"
    print(f"  Balance:    Expected={expected['balance']}, Got={extracted['balance']} [{match_b}]")

# Check final balance
print("\n" + "=" * 100)
print("OVERALL VALIDATION")
print("=" * 100)

# From PDF: Opening balance 8000.00, Closing balance 9754.64
expected_opening = 8000.00
expected_closing = 9754.64

if transactions:
    # Find first balance that's not from "Balance Brought Forward"
    first_balance = None
    for t in transactions:
        if t['balance'] and "Balance Brought Forward" not in t['description']:
            first_balance = t['balance']
            break

    last_balance = transactions[-1]['balance']

    print(f"\nExpected Opening Balance: SGD {expected_opening:,.2f}")
    print(f"Expected Closing Balance: SGD {expected_closing:,.2f}")
    print(f"Expected Change:          SGD {expected_closing - expected_opening:,.2f}")

    print(f"\nExtracted Last Balance:   SGD {last_balance:,.2f}")
    balance_match = "OK" if abs(last_balance - expected_closing) < 0.01 else "MISMATCH"
    print(f"Balance Validation:       [{balance_match}]")

print("\n" + "=" * 100)
