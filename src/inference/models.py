"""
Pydantic models for inference layer

Provides type-safe structures for inference results with method transparency.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class InferenceMethod(str, Enum):
    """How the inference was performed"""
    KEYWORD_MATCH = "keyword_match"
    SLM = "slm"
    HITL_REQUIRED = "hitl_required"
    NOT_ATTEMPTED = "not_attempted"


class DiagnosisInference(BaseModel):
    """
    Inferred diagnosis code with method transparency.

    Attributes:
        code: Diagnosis code (e.g., F45, C32) or None if not resolved
        description: Human-readable description of the code
        method: How the inference was performed
        confidence: Confidence score (0.0-1.0)
        matched_keywords: Keywords that matched (for keyword_match method)
        raw_text: Original diagnosis text from invoice
        slm_reasoning: SLM explanation if method=slm
    """
    code: Optional[str] = None
    description: Optional[str] = None
    method: InferenceMethod = InferenceMethod.NOT_ATTEMPTED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_keywords: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    slm_reasoning: Optional[str] = None


class BenefitInference(BaseModel):
    """
    Inferred benefit category and type with method transparency.

    Attributes:
        category: Benefit category (outpatient, inpatient, flex, others)
        category_description: Human-readable category description
        type_code: Benefit type code (OC, TCM, HSP, etc.)
        type_description: Human-readable type description
        method: How the inference was performed
        confidence: Confidence score (0.0-1.0)
        matched_keywords: Keywords that matched (for keyword_match method)
        provider_name: Original provider name from invoice
        slm_reasoning: SLM explanation if method=slm
    """
    category: Optional[str] = None
    category_description: Optional[str] = None
    type_code: Optional[str] = None
    type_description: Optional[str] = None
    method: InferenceMethod = InferenceMethod.NOT_ATTEMPTED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_keywords: List[str] = Field(default_factory=list)
    provider_name: Optional[str] = None
    slm_reasoning: Optional[str] = None


class InferenceResult(BaseModel):
    """
    Complete inference result for a parsed invoice.

    Attributes:
        diagnosis: Inferred diagnosis information
        benefit: Inferred benefit category and type
        hitl_required: List of fields that genuinely cannot be resolved
        inference_attempted: Whether inference was attempted
        inference_error: Error message if inference failed
    """
    diagnosis: DiagnosisInference = Field(default_factory=DiagnosisInference)
    benefit: BenefitInference = Field(default_factory=BenefitInference)
    hitl_required: List[str] = Field(
        default_factory=list,
        description="Fields that genuinely cannot be resolved automatically"
    )
    inference_attempted: bool = True
    inference_error: Optional[str] = None


# SLM Response Models (used by slm_client.py with instructor)
class SLMDiagnosisResponse(BaseModel):
    """Structured response for diagnosis inference from SLM"""
    code: Optional[str] = Field(
        default=None,
        description="Diagnosis code (e.g., F45, C32) or null if cannot determine"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the diagnosis code"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this inference (0.0-1.0)"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of how this code was determined"
    )


class SLMBenefitResponse(BaseModel):
    """Structured response for benefit type inference from SLM"""
    category: Optional[str] = Field(
        default=None,
        description="Benefit category (outpatient, inpatient, flex, others)"
    )
    type_code: Optional[str] = Field(
        default=None,
        description="Benefit type code (OC, TCM, HSP, etc.)"
    )
    type_description: Optional[str] = Field(
        default=None,
        description="Description of the benefit type"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this inference (0.0-1.0)"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of how this was determined"
    )
