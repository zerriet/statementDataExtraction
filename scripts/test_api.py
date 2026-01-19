"""
Test script for Medical Invoice Parser API

Usage:
    1. Start the server: uv run uvicorn src.api.medical_invoice_api:app --reload
    2. Run this script: uv run python scripts/test_api.py
"""

import httpx
import base64
import json
from pathlib import Path

API_URL = "http://127.0.0.1:8000"


def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    response = httpx.get(f"{API_URL}/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    return response.status_code == 200


def test_parse_upload(pdf_path: str):
    """Test file upload parsing endpoint"""
    print(f"\nTesting /parse endpoint with {Path(pdf_path).name}...")

    with open(pdf_path, "rb") as f:
        files = {"file": (Path(pdf_path).name, f, "application/pdf")}
        response = httpx.post(f"{API_URL}/parse", files=files)

    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  Invoice #: {result['extracted']['invoiceNumber']}")
        print(f"  Total: {result['extracted']['currency']} {result['extracted']['paymentAmount']}")
        print(f"  Confidence: {result['metadata']['confidence']:.0%}")
    else:
        print(f"  Error: {response.text}")

    return response.status_code == 200


def test_parse_base64(pdf_path: str):
    """Test base64 parsing endpoint"""
    print(f"\nTesting /parse/base64 endpoint with {Path(pdf_path).name}...")

    with open(pdf_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    payload = {
        "file_content": content,
        "filename": Path(pdf_path).name
    }

    response = httpx.post(f"{API_URL}/parse/base64", json=payload)

    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  Invoice #: {result['extracted']['invoiceNumber']}")
        print(f"  Total: {result['extracted']['currency']} {result['extracted']['paymentAmount']}")
        print(f"  Confidence: {result['metadata']['confidence']:.0%}")
        print(f"\n  Full JSON response:")
        print(json.dumps(result, indent=2))
    else:
        print(f"  Error: {response.text}")

    return response.status_code == 200


def main():
    print("=" * 60)
    print("Medical Invoice Parser API - Test Suite")
    print("=" * 60)

    # Test health
    if not test_health():
        print("\nAPI not reachable. Start server with:")
        print("  uv run uvicorn src.api.medical_invoice_api:app --reload")
        return

    # Test invoices
    invoice_dir = Path("resources/statements/medical_invoice_statements")
    invoice_files = list(invoice_dir.glob("*.pdf"))

    if not invoice_files:
        print(f"\nNo PDF files found in {invoice_dir}")
        return

    # Test file upload endpoint
    for pdf_path in invoice_files:
        test_parse_upload(str(pdf_path))

    # Test base64 endpoint (with first invoice only)
    test_parse_base64(str(invoice_files[0]))

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
