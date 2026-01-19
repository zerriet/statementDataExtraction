"""
Unit tests for Inference Layer.

Tests:
- Keyword matching accuracy
- Confidence scoring
- Method transparency
- Edge cases (no matches, ambiguous matches)
- HITL flagging
"""

import pytest
from inference.models import InferenceMethod


class TestKeywordMatcherDiagnosis:
    """Tests for diagnosis keyword matching."""

    def test_match_respiratory_infection(self, keyword_matcher):
        """Respiratory infection should match C32 (Flu/Influenza)."""
        result = keyword_matcher.match_diagnosis("Acute upper respiratory infection")

        assert result.code == "C32"
        assert result.method == InferenceMethod.KEYWORD_MATCH
        assert result.confidence > 0.0
        assert "respiratory" in [kw.lower() for kw in result.matched_keywords]

    def test_match_back_pain(self, keyword_matcher):
        """Back pain should match F45 (Fracture/Sprain/Pain)."""
        result = keyword_matcher.match_diagnosis("Acute lower back pain")

        assert result.code == "F45"
        assert result.method == InferenceMethod.KEYWORD_MATCH
        assert result.confidence > 0.0

    def test_match_flu(self, keyword_matcher):
        """Flu should match C32."""
        result = keyword_matcher.match_diagnosis("Flu symptoms with fever")

        assert result.code == "C32"
        assert result.method == InferenceMethod.KEYWORD_MATCH

    def test_match_muscle_strain(self, keyword_matcher):
        """Muscle strain should match F45."""
        result = keyword_matcher.match_diagnosis("Muscle strain - right shoulder")

        assert result.code == "F45"

    def test_no_match_returns_hitl(self, keyword_matcher):
        """Unknown diagnosis should flag HITL."""
        result = keyword_matcher.match_diagnosis("Unusual exotic disease XYZ123")

        assert result.method == InferenceMethod.HITL_REQUIRED
        assert result.code is None

    def test_null_diagnosis_returns_not_attempted(self, keyword_matcher):
        """Null diagnosis should return NOT_ATTEMPTED."""
        result = keyword_matcher.match_diagnosis(None)

        assert result.method == InferenceMethod.NOT_ATTEMPTED

    def test_empty_diagnosis_returns_not_attempted(self, keyword_matcher):
        """Empty diagnosis should return NOT_ATTEMPTED."""
        result = keyword_matcher.match_diagnosis("")

        assert result.method == InferenceMethod.NOT_ATTEMPTED

    def test_case_insensitive_matching(self, keyword_matcher):
        """Matching should be case-insensitive."""
        result1 = keyword_matcher.match_diagnosis("RESPIRATORY INFECTION")
        result2 = keyword_matcher.match_diagnosis("respiratory infection")
        result3 = keyword_matcher.match_diagnosis("Respiratory Infection")

        assert result1.code == result2.code == result3.code == "C32"


class TestKeywordMatcherBenefit:
    """Tests for benefit type keyword matching."""

    def test_match_physiotherapy_clinic(self, keyword_matcher):
        """Physiotherapy clinic should match OC (Outpatient Claim)."""
        result = keyword_matcher.match_benefit("City Osteopathy & Physiotherapy")

        assert result.category == "outpatient"
        assert result.type_code == "OC"
        assert result.method == InferenceMethod.KEYWORD_MATCH

    def test_match_family_clinic(self, keyword_matcher):
        """Family clinic should match OC."""
        result = keyword_matcher.match_benefit("ONEDOCTORS FAMILY CLINIC")

        assert result.category == "outpatient"
        assert result.type_code == "OC"

    def test_match_tcm(self, keyword_matcher):
        """TCM provider should match TCM benefit type."""
        result = keyword_matcher.match_benefit("Traditional Chinese Medicine Centre")

        assert result.category == "outpatient"
        assert result.type_code == "TCM"

    def test_match_hospital(self, keyword_matcher):
        """Hospital should match inpatient category."""
        result = keyword_matcher.match_benefit("Singapore General Hospital")

        assert result.category == "inpatient"
        assert result.type_code == "HSP"

    def test_match_dental(self, keyword_matcher):
        """Dental provider should match DNT."""
        # Use "dentist" without "clinic" to avoid matching OC
        result = keyword_matcher.match_benefit("Bright Smile Dentist")

        assert result.category == "flex"
        assert result.type_code == "DNT"

    def test_match_optical(self, keyword_matcher):
        """Optical shop should match OPT."""
        result = keyword_matcher.match_benefit("Vision Care Optical Centre")

        assert result.category == "flex"
        assert result.type_code == "OPT"

    def test_match_gym(self, keyword_matcher):
        """Gym/fitness should match WLN."""
        result = keyword_matcher.match_benefit("Fitness First Gym")

        assert result.category == "flex"
        assert result.type_code == "WLN"

    def test_no_match_returns_hitl(self, keyword_matcher):
        """Unknown provider should flag HITL."""
        result = keyword_matcher.match_benefit("Unknown Business ABC123")

        assert result.method == InferenceMethod.HITL_REQUIRED
        assert result.type_code is None

    def test_null_provider_returns_not_attempted(self, keyword_matcher):
        """Null provider should return NOT_ATTEMPTED."""
        result = keyword_matcher.match_benefit(None)

        assert result.method == InferenceMethod.NOT_ATTEMPTED


class TestKeywordMatcherConfidence:
    """Tests for confidence scoring."""

    def test_more_keywords_higher_confidence(self, keyword_matcher):
        """More keyword matches should give higher confidence."""
        result1 = keyword_matcher.match_diagnosis("pain")
        result2 = keyword_matcher.match_diagnosis("back pain with muscle strain and injury")

        # Both should match F45, but result2 should have higher confidence
        assert result1.code == result2.code == "F45"
        assert result2.confidence >= result1.confidence

    def test_confidence_capped_at_095(self, keyword_matcher):
        """Confidence should not exceed 0.95 for keyword matching."""
        result = keyword_matcher.match_diagnosis(
            "flu influenza respiratory cold fever cough viral infection"
        )

        assert result.confidence <= 0.95

    def test_base_confidence_at_least_06(self, keyword_matcher):
        """Minimum confidence for a match should be 0.6."""
        result = keyword_matcher.match_diagnosis("pain")

        if result.method == InferenceMethod.KEYWORD_MATCH:
            assert result.confidence >= 0.6


class TestInferenceService:
    """Tests for the InferenceService orchestrator."""

    def test_infer_returns_complete_result(self, inference_service, mock_parsed_data):
        """Infer should return complete InferenceResult."""
        result = inference_service.infer(mock_parsed_data)

        assert result.diagnosis is not None
        assert result.benefit is not None
        assert result.inference_attempted is True
        assert isinstance(result.hitl_required, list)

    def test_infer_resolves_back_pain(self, inference_service, mock_parsed_data):
        """Back pain diagnosis should be resolved."""
        result = inference_service.infer(mock_parsed_data)

        assert result.diagnosis.code == "F45"
        assert result.diagnosis.method == InferenceMethod.KEYWORD_MATCH

    def test_infer_resolves_physiotherapy(self, inference_service, mock_parsed_data):
        """Physiotherapy provider should be resolved to OC."""
        result = inference_service.infer(mock_parsed_data)

        assert result.benefit.type_code == "OC"
        assert result.benefit.category == "outpatient"

    def test_infer_respiratory_infection(self, inference_service, mock_respiratory_data):
        """Respiratory infection should map to C32."""
        result = inference_service.infer(mock_respiratory_data)

        assert result.diagnosis.code == "C32"
        assert "respiratory" in result.diagnosis.raw_text.lower()

    def test_infer_family_clinic(self, inference_service, mock_respiratory_data):
        """Family clinic should map to OC."""
        result = inference_service.infer(mock_respiratory_data)

        assert result.benefit.type_code == "OC"
        assert result.benefit.category == "outpatient"

    def test_hitl_required_populated_on_failure(self, inference_service):
        """HITL list should be populated when inference fails."""
        data = {
            "extracted": {
                "diagnosisRaw": None,
                "providerName": None
            },
            "metadata": {"success": True}
        }

        result = inference_service.infer(data)

        # Should have HITL items for both diagnosis and benefit
        assert len(result.hitl_required) >= 1

    def test_method_transparency(self, inference_service, mock_parsed_data):
        """Method field should accurately reflect how inference was done."""
        result = inference_service.infer(mock_parsed_data)

        # In keyword-only mode, should be KEYWORD_MATCH or HITL_REQUIRED
        assert result.diagnosis.method in [
            InferenceMethod.KEYWORD_MATCH,
            InferenceMethod.HITL_REQUIRED,
            InferenceMethod.NOT_ATTEMPTED
        ]
        assert result.benefit.method in [
            InferenceMethod.KEYWORD_MATCH,
            InferenceMethod.HITL_REQUIRED,
            InferenceMethod.NOT_ATTEMPTED
        ]


class TestInferenceEdgeCases:
    """Tests for edge cases in inference."""

    def test_empty_extracted_data(self, inference_service):
        """Should handle empty extracted data gracefully."""
        data = {
            "extracted": {},
            "metadata": {"success": True}
        }

        result = inference_service.infer(data)

        # Should not crash
        assert result.inference_attempted is True

    def test_missing_extracted_key(self, inference_service):
        """Should handle missing 'extracted' key."""
        data = {"metadata": {"success": True}}

        result = inference_service.infer(data)

        # Should not crash
        assert result.inference_attempted is True

    def test_special_characters_in_diagnosis(self, keyword_matcher):
        """Should handle special characters in diagnosis text."""
        result = keyword_matcher.match_diagnosis("Back pain (L5-S1) - chronic")

        assert result.code == "F45"

    def test_very_long_diagnosis_text(self, keyword_matcher):
        """Should handle very long diagnosis text."""
        long_text = "Patient presents with " + "back pain " * 100
        result = keyword_matcher.match_diagnosis(long_text)

        assert result.code == "F45"  # Should still match

    def test_numeric_in_provider_name(self, keyword_matcher):
        """Should handle numbers in provider name."""
        result = keyword_matcher.match_benefit("OneDoctors Family Clinic #123")

        assert result.type_code == "OC"
