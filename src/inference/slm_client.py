"""
OpenAI GPT-4o-mini client for structured inference

Uses instructor library for Pydantic-validated outputs.
Only called when keyword matching fails.
"""

import logging
from typing import List, Dict, Optional

from .config import InferenceSettings
from .models import SLMDiagnosisResponse, SLMBenefitResponse

logger = logging.getLogger(__name__)


class SLMClient:
    """
    OpenAI GPT-4o-mini client with instructor for structured outputs.

    Only instantiated when:
    1. INFERENCE_OPENAI_API_KEY is set
    2. INFERENCE_ENABLE_SLM_FALLBACK is true
    3. Keyword matching failed

    Usage:
        settings = InferenceSettings()
        client = SLMClient(settings)
        response = client.infer_diagnosis(raw_text, available_codes)
    """

    def __init__(self, settings: InferenceSettings):
        """
        Initialize SLM client.

        Args:
            settings: InferenceSettings with OpenAI configuration.

        Raises:
            ImportError: If openai or instructor not installed
            ValueError: If API key not configured
        """
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        self.settings = settings

        # Lazy import to avoid dependency issues when SLM not used
        try:
            import instructor
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "SLM dependencies not installed. "
                "Run: uv sync --group llm"
            ) from e

        # Initialize OpenAI client with instructor
        self._client = instructor.from_openai(
            OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout,
                max_retries=settings.openai_max_retries,
            )
        )
        self._model = settings.openai_model

        logger.info(f"SLM client initialized with model: {self._model}")

    def infer_diagnosis(
        self,
        raw_text: str,
        available_codes: List[Dict],
    ) -> SLMDiagnosisResponse:
        """
        Infer diagnosis code using SLM.

        Args:
            raw_text: Raw diagnosis text from invoice
            available_codes: List of valid diagnosis codes with descriptions
                            [{"code": "F45", "description": "...", "keywords": [...]}]

        Returns:
            SLMDiagnosisResponse with structured inference
        """
        codes_str = "\n".join(
            [f"- {d['code']}: {d['description']}" for d in available_codes]
        )

        logger.debug(f"SLM diagnosis inference for: {raw_text[:50]}...")

        response = self._client.chat.completions.create(
            model=self._model,
            response_model=SLMDiagnosisResponse,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a medical claims processing assistant. "
                        "Map the raw diagnosis text to the most appropriate diagnosis code. "
                        "If no code is appropriate, return null for code and set confidence below 0.5. "
                        "Be conservative - only return a code if you are reasonably confident."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Raw diagnosis text: \"{raw_text}\"\n\n"
                        f"Available diagnosis codes:\n{codes_str}\n\n"
                        "Select the most appropriate code or indicate if none apply."
                    ),
                },
            ],
        )

        logger.debug(
            f"SLM diagnosis response: code={response.code}, "
            f"confidence={response.confidence:.2f}"
        )

        return response

    def infer_benefit(
        self,
        provider_name: str,
        line_items: List[Dict],
        available_categories: Dict,
    ) -> SLMBenefitResponse:
        """
        Infer benefit category and type using SLM.

        Args:
            provider_name: Provider/clinic name
            line_items: List of invoice line items
                       [{"description": "...", "amount": ...}]
            available_categories: Benefit category structure from template

        Returns:
            SLMBenefitResponse with structured inference
        """
        # Format available options
        options_str = ""
        for cat_key, cat_config in available_categories.items():
            options_str += f"\nCategory: {cat_key} ({cat_config.get('description', '')})\n"
            for bt in cat_config.get("benefitTypes", []):
                options_str += f"  - {bt['code']}: {bt['description']}\n"

        # Format line items
        items_str = ", ".join(
            [item.get("description", "Unknown") for item in (line_items or [])]
        )
        if not items_str:
            items_str = "(no line items)"

        logger.debug(f"SLM benefit inference for provider: {provider_name}")

        response = self._client.chat.completions.create(
            model=self._model,
            response_model=SLMBenefitResponse,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a medical claims processing assistant. "
                        "Determine the benefit category and type based on the provider name "
                        "and services rendered. If unsure, return null and set confidence below 0.5. "
                        "Be conservative - only return a result if you are reasonably confident."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Provider name: \"{provider_name}\"\n"
                        f"Services/Items: {items_str}\n\n"
                        f"Available benefit types:\n{options_str}\n\n"
                        "Select the most appropriate benefit category and type."
                    ),
                },
            ],
        )

        logger.debug(
            f"SLM benefit response: {response.category}/{response.type_code}, "
            f"confidence={response.confidence:.2f}"
        )

        return response
