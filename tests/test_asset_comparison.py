import json
import pytest
from core.comparator import compare_resources
from core.reporter import generate_report


class TestFireflyAssetManagement:

    def test_comparison_runs_without_error(self, cloud_resources, iac_resources):
        """Smoke test: comparison should complete without exceptions."""
        results = compare_resources(cloud_resources, iac_resources)
        assert results is not None
        assert isinstance(results, list)

    def test_all_cloud_resources_are_analyzed(self, cloud_resources, iac_resources):
        """Every cloud resource must appear in the output."""
        results = compare_resources(cloud_resources, iac_resources)
        assert len(results) == len(cloud_resources), (
            f"Expected {len(cloud_resources)} results, got {len(results)}"
        )

    def test_state_values_are_valid(self, cloud_resources, iac_resources):
        """Each result's State must be one of the allowed values."""
        valid_states = {"Missing", "Match", "Modified"}
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            assert item.State in valid_states, (
                f"Invalid state '{item.State}' for resource {item.CloudResourceItem.get('id')}"
            )

    def test_missing_resources_have_no_iac_item(self, cloud_resources, iac_resources):
        """Resources with State=Missing must have IacResourceItem=None."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Missing":
                assert item.IacResourceItem is None

    def test_modified_resources_have_changelog(self, cloud_resources, iac_resources):
        """Resources with State=Modified must have at least one ChangeLog entry."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Modified":
                assert len(item.ChangeLog) > 0, (
                    f"Modified resource {item.CloudResourceItem.get('id')} has empty ChangeLog"
                )

    def test_match_resources_have_empty_changelog(self, cloud_resources, iac_resources):
        """Resources with State=Match must have an empty ChangeLog."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Match":
                assert item.ChangeLog == []

    def test_report_is_generated(self, cloud_resources, iac_resources, tmp_path):
        """Report file should be written with correct structure."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        assert output.exists()
        assert "summary" in report
        assert "results" in report
        assert report["summary"]["total"] == len(cloud_resources)

    def test_report_summary_counts_are_correct(self, cloud_resources, iac_resources, tmp_path):
        """Summary counts must add up to total."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        s = report["summary"]
        assert s["match"] + s["modified"] + s["missing"] == s["total"]

    def test_generate_persistent_report(self, cloud_resources, iac_resources):
        """Writes the final comparison report to reports/ directory for review."""
        from pathlib import Path

        output_path = Path(__file__).parent.parent / "reports" / "comparison_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = compare_resources(cloud_resources, iac_resources)
        report = generate_report(results, str(output_path))

        assert output_path.exists(), "Report file was not created"
        assert output_path.stat().st_size > 0, "Report file is empty"
        assert "summary" in report
        assert "results" in report