"""
Inference Service Orchestrator

Coordinates the inference pipeline:
1. Rule-based keyword matching (fast, free)
2. SLM fallback (when keywords don't match)
3. HITL flagging (when SLM confidence is low)
"""

import logging
from typing import Optional, List

from .config import InferenceSettings
from .models import (
    InferenceResult,
    DiagnosisInference,
    BenefitInference,
    InferenceMethod,
)
from .keyword_matcher import KeywordMatcher
from .slm_client import SLMClient

logger = logging.getLogger(__name__)


class InferenceService:
    """
    Orchestrates the inference pipeline.

    Pipeline:
        1. KeywordMatcher.match_*() - fast, deterministic
        2. SLMClient.infer_*() - only if keywords fail and SLM enabled
        3. Flag HITL - if SLM confidence < threshold or SLM disabled

    Usage:
        # Keyword-only mode
        service = InferenceService()
        result = service.infer(parsed_data)

        # With SLM fallback
        settings = InferenceSettings()
        service = InferenceService(settings)
        result = service.infer(parsed_data)
    """

    def __init__(self, settings: Optional[InferenceSettings] = None):
        """
        Initialize inference service.

        Args:
            settings: Configuration for SLM client.
                     If None or API key missing, runs in keyword-only mode.
        """
        self.settings = settings
        self.keyword_matcher = KeywordMatcher()
        self._slm_client: Optional[SLMClient] = None

        # Lazy-init SLM client only if settings provided and SLM available
        if settings and settings.slm_available:
            try:
                self._slm_client = SLMClient(settings)
                logger.info("Inference service initialized with SLM fallback")
            except Exception as e:
                logger.warning(f"SLM client init failed, keyword-only mode: {e}")
        else:
            logger.info("Inference service initialized in keyword-only mode")

    @property
    def slm_enabled(self) -> bool:
        """Check if SLM fallback is available"""
        return self._slm_client is not None

    def infer(self, parsed_data: dict) -> InferenceResult:
        """
        Perform inference on parsed invoice data.

        Args:
            parsed_data: Output from MedicalInvoiceParser.parse().to_json()
                        Expected structure: {"extracted": {...}, "metadata": {...}}

        Returns:
            InferenceResult with inferred fields and method transparency
        """
        # Handle malformed input: ensure extracted is a dict
        extracted = parsed_data.get("extracted") if parsed_data else None
        if not isinstance(extracted, dict):
            extracted = {}

        hitl_required: List[str] = []

        # Step 1: Infer diagnosis code
        diagnosis = self._infer_diagnosis(
            raw_text=extracted.get("diagnosisRaw"),
            hitl_required=hitl_required,
        )

        # Step 2: Infer benefit category and type
        benefit = self._infer_benefit(
            provider_name=extracted.get("providerName"),
            line_items=extracted.get("lineItems"),
            hitl_required=hitl_required,
        )

        return InferenceResult(
            diagnosis=diagnosis,
            benefit=benefit,
            hitl_required=hitl_required,
            inference_attempted=True,
            inference_error=None,
        )

    def _infer_diagnosis(
        self,
        raw_text: Optional[str],
        hitl_required: List[str],
    ) -> DiagnosisInference:
        """
        Infer diagnosis code with keyword -> SLM -> HITL fallback.

        Args:
            raw_text: Raw diagnosis text from invoice
            hitl_required: List to append HITL items to (mutated)

        Returns:
            DiagnosisInference with method transparency
        """
        # Step 1: Try keyword matching
        result = self.keyword_matcher.match_diagnosis(raw_text)

        if result.method == InferenceMethod.KEYWORD_MATCH:
            logger.debug(f"Diagnosis resolved by keywords: {result.code}")
            return result

        if result.method == InferenceMethod.NOT_ATTEMPTED:
            hitl_required.append("diagnosisCode: no diagnosis text found in invoice")
            return result

        # Step 2: Try SLM fallback
        if self._slm_client and raw_text:
            try:
                slm_response = self._slm_client.infer_diagnosis(
                    raw_text=raw_text,
                    available_codes=self.keyword_matcher.diagnosis_codes,
                )

                # Check confidence threshold
                threshold = self.settings.slm_confidence_threshold if self.settings else 0.8
                if slm_response.confidence >= threshold and slm_response.code:
                    logger.debug(
                        f"Diagnosis resolved by SLM: {slm_response.code} "
                        f"(confidence={slm_response.confidence:.2f})"
                    )
                    return DiagnosisInference(
                        code=slm_response.code,
                        description=slm_response.description,
                        method=InferenceMethod.SLM,
                        confidence=slm_response.confidence,
                        raw_text=raw_text,
                        slm_reasoning=slm_response.reasoning,
                    )
                else:
                    logger.debug(
                        f"SLM diagnosis confidence too low: {slm_response.confidence:.2f}"
                    )

            except Exception as e:
                logger.warning(f"SLM diagnosis inference failed: {e}")

        # Step 3: Flag for HITL
        hitl_required.append(
            f"diagnosisCode: could not map '{raw_text[:50]}...' to a code"
            if raw_text and len(raw_text) > 50
            else f"diagnosisCode: could not map '{raw_text}' to a code"
        )
        return DiagnosisInference(
            method=InferenceMethod.HITL_REQUIRED,
            confidence=0.0,
            raw_text=raw_text,
        )

    def _infer_benefit(
        self,
        provider_name: Optional[str],
        line_items: Optional[List[dict]],
        hitl_required: List[str],
    ) -> BenefitInference:
        """
        Infer benefit type with keyword -> SLM -> HITL fallback.

        Args:
            provider_name: Provider/clinic name from invoice
            line_items: List of invoice line items
            hitl_required: List to append HITL items to (mutated)

        Returns:
            BenefitInference with method transparency
        """
        # Step 1: Try keyword matching
        result = self.keyword_matcher.match_benefit(provider_name)

        if result.method == InferenceMethod.KEYWORD_MATCH:
            logger.debug(f"Benefit resolved by keywords: {result.type_code}")
            return result

        if result.method == InferenceMethod.NOT_ATTEMPTED:
            hitl_required.append("benefitType: no provider name found")
            return result

        # Step 2: Try SLM fallback
        if self._slm_client and provider_name:
            try:
                slm_response = self._slm_client.infer_benefit(
                    provider_name=provider_name,
                    line_items=line_items or [],
                    available_categories=self.keyword_matcher.benefit_categories,
                )

                threshold = self.settings.slm_confidence_threshold if self.settings else 0.8
                if slm_response.confidence >= threshold and slm_response.type_code:
                    logger.debug(
                        f"Benefit resolved by SLM: {slm_response.category}/{slm_response.type_code} "
                        f"(confidence={slm_response.confidence:.2f})"
                    )
                    return BenefitInference(
                        category=slm_response.category,
                        type_code=slm_response.type_code,
                        type_description=slm_response.type_description,
                        method=InferenceMethod.SLM,
                        confidence=slm_response.confidence,
                        provider_name=provider_name,
                        slm_reasoning=slm_response.reasoning,
                    )
                else:
                    logger.debug(
                        f"SLM benefit confidence too low: {slm_response.confidence:.2f}"
                    )

            except Exception as e:
                logger.warning(f"SLM benefit inference failed: {e}")

        # Step 3: Flag for HITL
        hitl_required.append(
            f"benefitType: could not determine from provider '{provider_name}'"
        )
        return BenefitInference(
            method=InferenceMethod.HITL_REQUIRED,
            confidence=0.0,
            provider_name=provider_name,
        )
