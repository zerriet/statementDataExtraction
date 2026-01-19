"""
Inference Configuration using pydantic-settings

Manages OpenAI API credentials and inference behavior settings.
Loads from environment variables with INFERENCE_ prefix.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class InferenceSettings(BaseSettings):
    """
    Settings for the SLM inference layer.

    Environment variables (prefix: INFERENCE_):
        INFERENCE_OPENAI_API_KEY: OpenAI API key
        INFERENCE_OPENAI_MODEL: Model name (default: gpt-4o-mini)
        INFERENCE_OPENAI_TIMEOUT: Request timeout in seconds
        INFERENCE_OPENAI_MAX_RETRIES: Max retries on failure
        INFERENCE_ENABLE_SLM_FALLBACK: Enable SLM when keywords don't match
        INFERENCE_SLM_CONFIDENCE_THRESHOLD: Minimum confidence to accept SLM result
    """

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT-4o-mini. If not set, keyword-only mode."
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Model to use for inference"
    )
    openai_timeout: float = Field(
        default=30.0,
        description="Request timeout in seconds"
    )
    openai_max_retries: int = Field(
        default=2,
        description="Max retries on transient failures"
    )

    # Inference Behavior
    enable_slm_fallback: bool = Field(
        default=True,
        description="Enable SLM fallback when keywords don't match"
    )
    slm_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for SLM inference to be accepted"
    )

    model_config = {
        "env_prefix": "INFERENCE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def slm_available(self) -> bool:
        """Check if SLM is configured and enabled"""
        return bool(self.openai_api_key) and self.enable_slm_fallback
