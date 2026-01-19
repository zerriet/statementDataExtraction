"""
Stress tests for Medical Invoice Parser.

Tests:
- Concurrent request handling
- Large batch processing
- Memory usage
- Repeated parsing (no state leakage)
- Various edge case inputs
"""

import pytest
import time
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TEST_DATA_DIR = Path(__file__).parent.parent / "resources" / "statements" / "medical_invoice_statements"


class TestParserStress:
    """Stress tests for the parser."""

    def test_repeated_parsing_no_state_leakage(self, parser, sample_invoice_paths):
        """Parsing same file multiple times should give consistent results."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        pdf_path = sample_invoice_paths[0]
        results = []

        # Parse same file 10 times
        for _ in range(10):
            result = parser.parse(str(pdf_path))
            results.append(result)

        # All results should be identical
        first = results[0]
        for i, result in enumerate(results[1:], 2):
            assert result.success == first.success, f"Success differs on parse #{i}"
            assert result.data == first.data, f"Data differs on parse #{i}"
            assert result.confidence == first.confidence, f"Confidence differs on parse #{i}"

    def test_new_parser_instance_per_file(self, sample_invoice_paths):
        """Fresh parser instance for each file should work correctly."""
        from parsers.medical_invoice_parser import MedicalInvoiceParser

        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        results = []
        for pdf_path in sample_invoice_paths:
            parser = MedicalInvoiceParser()  # Fresh instance
            result = parser.parse(str(pdf_path))
            results.append((pdf_path.name, result))

        # All should succeed
        for name, result in results:
            assert result.success is True, f"Failed to parse {name}"

    def test_batch_parsing_all_invoices(self, parser, sample_invoice_paths):
        """Should be able to parse all invoices in sequence."""
        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        success_count = 0
        fail_count = 0

        for pdf_path in sample_invoice_paths:
            result = parser.parse(str(pdf_path))
            if result.success:
                success_count += 1
            else:
                fail_count += 1

        # At least some should succeed
        assert success_count > 0, "No invoices parsed successfully"
        print(f"\nBatch results: {success_count} success, {fail_count} failed")


class TestKeywordMatcherStress:
    """Stress tests for keyword matching."""

    def test_many_diagnosis_matches(self, keyword_matcher):
        """Should handle many diagnosis lookups efficiently."""
        test_cases = [
            "back pain",
            "flu symptoms",
            "respiratory infection",
            "muscle strain",
            "fever and cough",
            "joint pain",
            "sore throat",
            "cold symptoms",
            "injury from fall",
            "sprained ankle",
        ] * 100  # 1000 total

        start = time.time()
        for diagnosis in test_cases:
            result = keyword_matcher.match_diagnosis(diagnosis)
            assert result is not None

        elapsed = time.time() - start
        print(f"\n1000 diagnosis matches in {elapsed:.3f}s ({1000/elapsed:.0f}/sec)")

        # Should complete in reasonable time (<5 seconds)
        assert elapsed < 5.0, "Keyword matching too slow"

    def test_many_benefit_matches(self, keyword_matcher):
        """Should handle many benefit lookups efficiently."""
        test_cases = [
            "Family Clinic",
            "General Hospital",
            "Dental Care Centre",
            "Physiotherapy Clinic",
            "TCM Centre",
            "Optical Shop",
            "Fitness Gym",
            "Medical Centre",
            "Specialist Clinic",
            "Wellness Centre",
        ] * 100  # 1000 total

        start = time.time()
        for provider in test_cases:
            result = keyword_matcher.match_benefit(provider)
            assert result is not None

        elapsed = time.time() - start
        print(f"\n1000 benefit matches in {elapsed:.3f}s ({1000/elapsed:.0f}/sec)")

        assert elapsed < 5.0, "Keyword matching too slow"


class TestInferenceServiceStress:
    """Stress tests for the inference service."""

    def test_repeated_inference_consistent(self, inference_service, mock_parsed_data):
        """Repeated inference should give consistent results."""
        results = []

        for _ in range(50):
            result = inference_service.infer(mock_parsed_data)
            results.append(result)

        # All should be identical
        first = results[0]
        for i, result in enumerate(results[1:], 2):
            assert result.diagnosis.code == first.diagnosis.code, \
                f"Diagnosis code differs on inference #{i}"
            assert result.benefit.type_code == first.benefit.type_code, \
                f"Benefit type differs on inference #{i}"

    def test_inference_batch_performance(self, inference_service, mock_parsed_data):
        """Should handle batch inference efficiently."""
        start = time.time()

        for _ in range(100):
            result = inference_service.infer(mock_parsed_data)
            assert result.inference_attempted is True

        elapsed = time.time() - start
        print(f"\n100 inferences in {elapsed:.3f}s ({100/elapsed:.0f}/sec)")

        assert elapsed < 10.0, "Inference too slow"


class TestEdgeCaseInputs:
    """Tests for various edge case inputs."""

    @pytest.mark.parametrize("diagnosis", [
        "",
        " ",
        "\n\n\n",
        "\t\t",
        "a" * 10000,  # Very long
        "back pain!@#$%^&*()",  # Special chars
        "123 456 789",  # Numbers only
        "UPPERCASE ONLY",
        "lowercase only",
        "MiXeD CaSe TeXt",
        "Unicode: café naïve résumé",
        "中文诊断",  # Chinese
        "日本語診断",  # Japanese
    ])
    def test_diagnosis_edge_cases(self, keyword_matcher, diagnosis):
        """Keyword matcher should handle various diagnosis inputs."""
        # Should not crash
        result = keyword_matcher.match_diagnosis(diagnosis)
        assert result is not None
        assert result.method is not None

    @pytest.mark.parametrize("provider", [
        "",
        " ",
        "a" * 10000,  # Very long
        "Clinic #123!@#",  # Special chars
        "123 Medical 456",
        "UPPERCASE CLINIC",
        "lowercase clinic",
        "Unicode: Clínic Médical",
        "诊所",  # Chinese
    ])
    def test_provider_edge_cases(self, keyword_matcher, provider):
        """Keyword matcher should handle various provider inputs."""
        # Should not crash
        result = keyword_matcher.match_benefit(provider)
        assert result is not None
        assert result.method is not None

    def test_malformed_parsed_data(self, inference_service):
        """Should handle malformed input data."""
        malformed_inputs = [
            {},
            {"extracted": None},
            {"extracted": "not a dict"},
            {"extracted": {"diagnosisRaw": 12345}},  # Wrong type
            {"extracted": {"providerName": [1, 2, 3]}},  # Wrong type
            {"metadata": None, "extracted": {}},
        ]

        for data in malformed_inputs:
            # Should not crash
            try:
                result = inference_service.infer(data)
                assert result is not None
            except Exception as e:
                pytest.fail(f"Crashed on malformed input: {data}, error: {e}")


class TestConcurrency:
    """Tests for concurrent access."""

    def test_concurrent_keyword_matching(self, keyword_matcher):
        """Multiple threads should be able to use keyword matcher safely."""
        diagnoses = ["back pain", "flu", "respiratory infection"] * 10
        results = []

        def match_diagnosis(text):
            return keyword_matcher.match_diagnosis(text)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(match_diagnosis, d) for d in diagnoses]
            for future in as_completed(futures):
                results.append(future.result())

        # All should complete successfully
        assert len(results) == len(diagnoses)
        for result in results:
            assert result is not None

    def test_concurrent_inference(self, inference_service, mock_parsed_data):
        """Multiple threads should be able to use inference service."""
        results = []

        def run_inference():
            return inference_service.infer(mock_parsed_data)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_inference) for _ in range(20)]
            for future in as_completed(futures):
                results.append(future.result())

        # All should complete
        assert len(results) == 20
        for result in results:
            assert result.inference_attempted is True


class TestMemory:
    """Tests for memory usage."""

    def test_no_memory_leak_on_repeated_parsing(self, sample_invoice_paths):
        """Memory should not grow unboundedly with repeated parsing."""
        import gc
        from parsers.medical_invoice_parser import MedicalInvoiceParser

        if not sample_invoice_paths:
            pytest.skip("No invoice PDFs found")

        pdf_path = sample_invoice_paths[0]

        # Force garbage collection
        gc.collect()

        # Parse many times
        for _ in range(100):
            parser = MedicalInvoiceParser()
            parser.parse(str(pdf_path))

        gc.collect()

        # If we get here without memory error, test passes
        # (Actual memory measurement would require psutil)

    def test_large_result_handling(self, inference_service):
        """Should handle results with large amounts of data."""
        # Create data with many line items
        large_data = {
            "extracted": {
                "diagnosisRaw": "back pain " * 100,
                "providerName": "Clinic " * 50,
                "lineItems": [
                    {"description": f"Item {i}", "amount": float(i)}
                    for i in range(1000)
                ]
            },
            "metadata": {"success": True}
        }

        result = inference_service.infer(large_data)
        assert result is not None
