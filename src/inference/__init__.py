"""
Inference Layer Module

Provides rule-based keyword matching with SLM fallback for medical invoice field inference.

Usage:
    from src.inference import InferenceService, InferenceSettings

    # Keyword-only mode (no API key needed)
    service = InferenceService()
    result = service.infer(parsed_data)

    # With SLM fallback
    settings = InferenceSettings()  # Loads from .env
    service = InferenceService(settings)
    result = service.infer(parsed_data)
"""

from .config import InferenceSettings
from .models import (
    InferenceMethod,
    DiagnosisInference,
    BenefitInference,
    InferenceResult,
)
from .keyword_matcher import KeywordMatcher
from .inference_service import InferenceService

__all__ = [
    "InferenceSettings",
    "InferenceMethod",
    "DiagnosisInference",
    "BenefitInference",
    "InferenceResult",
    "KeywordMatcher",
    "InferenceService",
]
