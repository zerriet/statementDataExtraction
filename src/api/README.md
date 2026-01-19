# Medical Invoice Parser API

REST API service for extracting structured data from medical invoice PDFs.

## Quick Start

```bash
# Install API dependencies
uv sync --group api

# Start the server
uv run uvicorn src.api.medical_invoice_api:app --reload

# Server runs at http://127.0.0.1:8000
```

## Endpoints

### Health Check
```
GET /health
```

### Parse Invoice (File Upload)
```
POST /parse
Content-Type: multipart/form-data

file: <PDF file>
```

### Parse Invoice (Base64)
```
POST /parse/base64
Content-Type: application/json

{
    "file_content": "<base64-encoded PDF>",
    "filename": "invoice.pdf"
}
```

## Response Format

All parse endpoints return the same JSON structure:

```json
{
    "extracted": {
        "invoiceNumber": "INV-2601000859",
        "visitDate": "2026-01-10",
        "providerName": "City Osteopathy & Physiotherapy",
        "patientName": "Mark Tan Jen Wei",
        "lineItems": [
            {"description": "Physiotherapy", "amount": 170.0}
        ],
        "subtotal": 170.0,
        "gstAmount": 15.30,
        "paymentAmount": 185.30,
        "currency": "SGD",
        "diagnosisRaw": null
    },
    "inference_required": [
        "diagnosisCode: no diagnosis found in invoice",
        "benefitType: requires inference from provider name",
        "benefitCategory: requires inference"
    ],
    "metadata": {
        "success": true,
        "confidence": 0.9,
        "warnings": [],
        "source_file": "invoice1.pdf",
        "abort_reason": null
    }
}
```

## Integration with Agentic Framework

### As a Tool Definition

```python
# Example tool definition for upstream LLM agent
{
    "name": "parse_medical_invoice",
    "description": "Extract structured data from a medical invoice PDF",
    "parameters": {
        "type": "object",
        "properties": {
            "file_content": {
                "type": "string",
                "description": "Base64-encoded PDF content"
            },
            "filename": {
                "type": "string",
                "description": "Original filename"
            }
        },
        "required": ["file_content"]
    }
}
```

### Example Agent Workflow

1. **User uploads invoice** → Agent receives file
2. **Agent calls parse API** → Gets extracted data + inference flags
3. **Agent performs inference** on flagged fields:
   - `diagnosisRaw` → map to `diagnosisCode` using enum
   - `providerName` → infer `benefitType` and `benefitCategory`
4. **Agent returns complete claim** → Ready for submission

## API Documentation

Interactive API docs available at:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Testing

```bash
# Run test script
uv run python scripts/test_api.py
```
