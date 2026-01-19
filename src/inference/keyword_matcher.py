"""
Rule-based keyword matching engine

Fast, deterministic, zero-cost inference using template keywords.
This is the first layer of inference - always runs before SLM.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from .models import (
    DiagnosisInference,
    BenefitInference,
    InferenceMethod,
)

logger = logging.getLogger(__name__)


class KeywordMatcher:
    """
    Rule-based inference using keyword mappings from template.

    Loads keyword mappings from claimSubmitTemplate2.json and matches
    extracted text against them. This is fast and deterministic.

    Usage:
        matcher = KeywordMatcher()
        diagnosis = matcher.match_diagnosis("Acute upper respiratory infection")
        benefit = matcher.match_benefit("City Osteopathy & Physiotherapy")
    """

    def __init__(self, template_path: Optional[Path] = None):
        """
        Initialize with keyword mappings from template.

        Args:
            template_path: Path to claimSubmitTemplate2.json.
                          Defaults to resources/jsonTemplates/claimSubmitTemplate2.json
        """
        if template_path is None:
            template_path = (
                Path(__file__).parent.parent.parent
                / "resources"
                / "jsonTemplates"
                / "claimSubmitTemplate2.json"
            )

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        self._enums = template.get("_enums", {})
        self._diagnosis_codes: List[Dict] = self._enums.get("diagnosisCode", [])
        self._benefit_categories: Dict = self._enums.get("benefitCategory", {})

        logger.debug(
            f"Loaded {len(self._diagnosis_codes)} diagnosis codes, "
            f"{len(self._benefit_categories)} benefit categories"
        )

    @property
    def diagnosis_codes(self) -> List[Dict]:
        """Get available diagnosis codes for SLM context"""
        return self._diagnosis_codes

    @property
    def benefit_categories(self) -> Dict:
        """Get available benefit categories for SLM context"""
        return self._benefit_categories

    def match_diagnosis(self, raw_text: Optional[str]) -> DiagnosisInference:
        """
        Match raw diagnosis text to diagnosis code using keywords.

        Args:
            raw_text: Raw diagnosis text from parser
                     (e.g., "Acute upper respiratory infection")

        Returns:
            DiagnosisInference with:
            - method=KEYWORD_MATCH if keywords matched
            - method=HITL_REQUIRED if no match found
            - method=NOT_ATTEMPTED if raw_text is None/empty
        """
        # Handle non-string or empty input
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return DiagnosisInference(
                method=InferenceMethod.NOT_ATTEMPTED,
                confidence=0.0,
                raw_text=None,
            )

        raw_lower = raw_text.lower()
        best_match: Optional[Dict] = None
        best_score = 0
        matched_keywords: List[str] = []

        for diagnosis in self._diagnosis_codes:
            code = diagnosis.get("code")
            keywords = diagnosis.get("keywords", [])

            # Count matching keywords
            matches = [kw for kw in keywords if kw.lower() in raw_lower]
            score = len(matches)

            if score > best_score:
                best_score = score
                best_match = diagnosis
                matched_keywords = matches

        if best_match and best_score > 0:
            # Calculate confidence based on keyword density
            # Base 0.6, +0.1 per keyword match, max 0.95
            confidence = min(0.95, 0.6 + (best_score * 0.1))

            logger.debug(
                f"Diagnosis keyword match: {best_match.get('code')} "
                f"(score={best_score}, confidence={confidence:.2f})"
            )

            return DiagnosisInference(
                code=best_match.get("code"),
                description=best_match.get("description"),
                method=InferenceMethod.KEYWORD_MATCH,
                confidence=confidence,
                matched_keywords=matched_keywords,
                raw_text=raw_text,
            )

        # No keyword match - needs SLM or HITL
        logger.debug(f"No diagnosis keyword match for: {raw_text[:50]}...")
        return DiagnosisInference(
            method=InferenceMethod.HITL_REQUIRED,
            confidence=0.0,
            raw_text=raw_text,
        )

    def match_benefit(self, provider_name: Optional[str]) -> BenefitInference:
        """
        Match provider name to benefit category and type using keywords.

        Args:
            provider_name: Provider/clinic name from parser
                          (e.g., "City Osteopathy & Physiotherapy")

        Returns:
            BenefitInference with:
            - method=KEYWORD_MATCH if keywords matched
            - method=HITL_REQUIRED if no match found
            - method=NOT_ATTEMPTED if provider_name is None/empty
        """
        # Handle non-string or empty input
        if not provider_name or not isinstance(provider_name, str) or not provider_name.strip():
            return BenefitInference(
                method=InferenceMethod.NOT_ATTEMPTED,
                confidence=0.0,
                provider_name=None,
            )

        provider_lower = provider_name.lower()
        best_category: Optional[Tuple[str, str]] = None  # (key, description)
        best_type: Optional[Dict] = None
        best_score = 0
        matched_keywords: List[str] = []

        for category_key, category_config in self._benefit_categories.items():
            # Check category-level keywords
            cat_keywords = category_config.get("keywords", [])
            cat_matches = [kw for kw in cat_keywords if kw.lower() in provider_lower]

            # Check benefit type keywords within category
            for benefit_type in category_config.get("benefitTypes", []):
                type_keywords = benefit_type.get("keywords", [])
                type_matches = [kw for kw in type_keywords if kw.lower() in provider_lower]

                total_score = len(cat_matches) + len(type_matches)

                if total_score > best_score:
                    best_score = total_score
                    best_category = (category_key, category_config.get("description", ""))
                    best_type = benefit_type
                    matched_keywords = cat_matches + type_matches

        if best_category and best_type and best_score > 0:
            confidence = min(0.95, 0.6 + (best_score * 0.1))

            logger.debug(
                f"Benefit keyword match: {best_category[0]}/{best_type.get('code')} "
                f"(score={best_score}, confidence={confidence:.2f})"
            )

            return BenefitInference(
                category=best_category[0],
                category_description=best_category[1],
                type_code=best_type.get("code"),
                type_description=best_type.get("description"),
                method=InferenceMethod.KEYWORD_MATCH,
                confidence=confidence,
                matched_keywords=matched_keywords,
                provider_name=provider_name,
            )

        # No keyword match - needs SLM or HITL
        logger.debug(f"No benefit keyword match for: {provider_name}")
        return BenefitInference(
            method=InferenceMethod.HITL_REQUIRED,
            confidence=0.0,
            provider_name=provider_name,
        )
