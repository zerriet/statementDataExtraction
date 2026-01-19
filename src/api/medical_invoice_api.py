"""
Medical Invoice Parser - FastAPI Service

Exposes the medical invoice parser as a REST API endpoint
for consumption by upstream agentic frameworks.

Endpoints:
    POST /parse          - Parse a single invoice (file upload)
    POST /parse/base64   - Parse a single invoice (base64 encoded)
    GET  /health         - Health check
    GET  /                - Test GUI (if gui/ folder exists)

Query Parameters:
    inference=true       - Enable inference layer (adds 'inferred' section)
"""

import base64
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys

# Add parent directory to path for imports (src directory)
_src_dir = str(Path(__file__).parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Try multiple import styles for Azure compatibility
try:
    from parsers.medical_invoice_parser import MedicalInvoiceParser
    from inference.config import InferenceSettings
    from inference.inference_service import InferenceService
except ImportError:
    from src.parsers.medical_invoice_parser import MedicalInvoiceParser
    from src.inference.config import InferenceSettings
    from src.inference.inference_service import InferenceService

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Medical Invoice Parser API",
    description="Extracts structured data from medical invoice PDFs for upstream agentic frameworks",
    version="1.0.0",
)

# Enable CORS for GUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GUI path
GUI_PATH = Path(__file__).parent.parent.parent / "gui"


# Request/Response Models
class Base64InvoiceRequest(BaseModel):
    """Request model for base64-encoded PDF"""
    file_content: str = Field(..., description="Base64-encoded PDF content")
    filename: Optional[str] = Field(default="invoice.pdf", description="Original filename")


class ExtractedData(BaseModel):
    """Extracted invoice data"""
    invoiceNumber: Optional[str] = None
    visitDate: Optional[str] = None
    providerName: Optional[str] = None
    patientName: Optional[str] = None
    lineItems: list = Field(default_factory=list)
    subtotal: Optional[float] = None
    gstAmount: Optional[float] = None
    paymentAmount: Optional[float] = None
    currency: str = "SGD"
    diagnosisRaw: Optional[str] = None


class Metadata(BaseModel):
    """Parsing metadata"""
    success: bool
    confidence: float
    warnings: list = Field(default_factory=list)
    source_file: Optional[str] = None
    abort_reason: Optional[str] = None


class ParseResponse(BaseModel):
    """Response model for parse endpoints"""
    extracted: ExtractedData
    inference_required: list = Field(
        default_factory=list,
        description="Fields that require LLM/rule-based inference by upstream framework"
    )
    metadata: Metadata

    class Config:
        json_schema_extra = {
            "example": {
                "extracted": {
                    "invoiceNumber": "INV-2601000859",
                    "visitDate": "2026-01-10",
                    "providerName": "City Osteopathy & Physiotherapy",
                    "patientName": "Mark Tan Jen Wei",
                    "lineItems": [{"description": "Physiotherapy", "amount": 170.0}],
                    "subtotal": 170.0,
                    "gstAmount": 15.30,
                    "paymentAmount": 185.30,
                    "currency": "SGD",
                    "diagnosisRaw": None
                },
                "inference_required": [
                    "diagnosisCode: no diagnosis found in invoice",
                    "benefitType: requires inference from provider name",
                    "benefitCategory: requires inference"
                ],
                "metadata": {
                    "success": True,
                    "confidence": 0.9,
                    "warnings": [],
                    "source_file": "invoice1.pdf",
                    "abort_reason": None
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str


# Template paths
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "resources" / "jsonTemplates"
AVAILABLE_TEMPLATES = {
    "v1": "claimSubmitTemplate.json",      # Basic template without keywords
    "v2": "claimSubmitTemplate2.json",     # Enhanced template with keyword mappings
}
DEFAULT_TEMPLATE = "v2"  # <-- CHANGE THIS TO SWAP DEFAULT TEMPLATE


# Inference service (lazy initialized)
_inference_service: Optional[InferenceService] = None


def get_inference_service() -> Optional[InferenceService]:
    """
    Lazy initialization of inference service.

    Returns:
        InferenceService if configuration available, None otherwise.
        Graceful degradation - returns None if API key not set.
    """
    global _inference_service
    if _inference_service is None:
        try:
            settings = InferenceSettings()
            _inference_service = InferenceService(settings)
            logger.info(
                f"Inference service initialized (SLM enabled: {_inference_service.slm_enabled})"
            )
        except Exception as e:
            # Graceful degradation - keyword-only mode
            logger.warning(f"Inference service init with settings failed: {e}")
            try:
                _inference_service = InferenceService(settings=None)
                logger.info("Inference service initialized in keyword-only mode")
            except Exception as e2:
                logger.error(f"Inference service unavailable: {e2}")
                return None
    return _inference_service


# Endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint for service monitoring"""
    return HealthResponse(
        status="healthy",
        service="medical-invoice-parser",
        version="1.0.0"
    )


@app.get("/template", tags=["Template"])
async def get_template(version: str = DEFAULT_TEMPLATE):
    """
    Get the claim submission template schema.

    The template includes:
    - Field structure for claim submission
    - _enums with keyword mappings for inference
    - _meta with usage instructions

    Args:
        version: Template version ("v1" = basic, "v2" = with keywords). Default: v2

    Use this to understand the expected output schema and
    perform inference on extracted fields.
    """
    if version not in AVAILABLE_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template version. Available: {list(AVAILABLE_TEMPLATES.keys())}"
        )

    template_file = TEMPLATE_PATH / AVAILABLE_TEMPLATES[version]

    if not template_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template file not found: {AVAILABLE_TEMPLATES[version]}"
        )

    import json
    with open(template_file, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.get("/template/list", tags=["Template"])
async def list_templates():
    """List available template versions"""
    return {
        "available": list(AVAILABLE_TEMPLATES.keys()),
        "default": DEFAULT_TEMPLATE,
        "templates": {
            "v1": "Basic template without keyword mappings",
            "v2": "Enhanced template with keyword mappings for inference"
        }
    }


@app.post("/parse", response_model=ParseResponse, tags=["Parser"])
async def parse_invoice_upload(
    file: UploadFile = File(..., description="PDF invoice file"),
    inference: bool = Query(
        default=False,
        description="Enable inference layer to resolve flagged fields (adds 'inferred' section)"
    ),
):
    """
    Parse a medical invoice PDF uploaded as multipart/form-data.

    Args:
        file: PDF invoice file
        inference: If true, runs inference layer to resolve diagnosisCode, benefitType, etc.

    Returns:
        Extracted data, optionally with inferred fields if inference=true.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    # Save uploaded file to temp location
    try:
        content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Parse the invoice
        parser = MedicalInvoiceParser()
        result = parser.parse(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        # Build response
        result_json = result.to_json(source_file=file.filename)

        # If inference requested, run inference layer
        if inference:
            inference_svc = get_inference_service()
            if inference_svc:
                inference_result = inference_svc.infer(result_json)
                result_json["inferred"] = inference_result.model_dump()
                # Update inference_required to only show HITL items
                result_json["inference_required"] = inference_result.hitl_required
            else:
                result_json["inferred"] = None
                result_json["metadata"]["warnings"].append(
                    "Inference unavailable: service not initialized"
                )

        # Return structured response
        return JSONResponse(content=result_json)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse invoice: {str(e)}"
        )


@app.post("/parse/base64", response_model=ParseResponse, tags=["Parser"])
async def parse_invoice_base64(
    request: Base64InvoiceRequest,
    inference: bool = Query(
        default=False,
        description="Enable inference layer to resolve flagged fields (adds 'inferred' section)"
    ),
):
    """
    Parse a medical invoice PDF provided as base64-encoded string.

    Useful for agentic frameworks that pass file content directly.

    Args:
        request: Base64-encoded PDF content and optional filename
        inference: If true, runs inference layer to resolve diagnosisCode, benefitType, etc.

    Returns:
        Extracted data, optionally with inferred fields if inference=true.
    """
    try:
        # Decode base64 content
        try:
            pdf_content = base64.b64decode(request.file_content)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid base64 encoding"
            )

        # Validate it's a PDF (check magic bytes)
        if not pdf_content.startswith(b'%PDF'):
            raise HTTPException(
                status_code=400,
                detail="Content does not appear to be a valid PDF"
            )

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name

        # Parse the invoice
        parser = MedicalInvoiceParser()
        result = parser.parse(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        # Build response
        result_json = result.to_json(source_file=request.filename)

        # If inference requested, run inference layer
        if inference:
            inference_svc = get_inference_service()
            if inference_svc:
                inference_result = inference_svc.infer(result_json)
                result_json["inferred"] = inference_result.model_dump()
                # Update inference_required to only show HITL items
                result_json["inference_required"] = inference_result.hitl_required
            else:
                result_json["inferred"] = None
                result_json["metadata"]["warnings"].append(
                    "Inference unavailable: service not initialized"
                )

        # Return structured response
        return JSONResponse(content=result_json)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse invoice: {str(e)}"
        )


# GUI Endpoint - Serve test interface
@app.get("/", response_class=HTMLResponse, tags=["GUI"], include_in_schema=False)
async def serve_gui():
    """Serve the test GUI interface"""
    gui_file = GUI_PATH / "index.html"

    if gui_file.exists():
        return FileResponse(gui_file, media_type="text/html")
    else:
        # Fallback: redirect to API docs
        return HTMLResponse(
            content="""
            <html>
                <head><meta http-equiv="refresh" content="0; url=/docs"></head>
                <body>
                    <p>GUI not found. Redirecting to <a href="/docs">API documentation</a>...</p>
                </body>
            </html>
            """,
            status_code=200
        )


# Run with: uvicorn src.api.medical_invoice_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
