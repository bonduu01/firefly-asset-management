from pathlib import Path

import pytest

from core.comparator import compare_resources
from core.reporter import generate_report


class TestFireflyAssetManagement:

    # =========================================================================
    # Core Comparison Tests
    # =========================================================================

    def test_comparison_runs_without_error(self, cloud_resources, iac_resources):
        """Smoke test: comparison must complete without raising any exception."""
        results = compare_resources(cloud_resources, iac_resources)
        assert results is not None
        assert isinstance(results, list)

    def test_all_cloud_resources_are_analyzed(self, cloud_resources, iac_resources):
        """Every cloud resource must produce exactly one result entry."""
        results = compare_resources(cloud_resources, iac_resources)
        assert len(results) == len(cloud_resources), (
            f"Expected {len(cloud_resources)} results, got {len(results)}"
        )

    def test_state_values_are_valid(self, cloud_resources, iac_resources):
        """Every result State must be one of: Match | Modified | Missing."""
        valid_states = {"Missing", "Match", "Modified"}
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            assert item.State in valid_states, (
                f"Invalid state '{item.State}' "
                f"for resource id={item.CloudResourceItem.get('id')}"
            )

    def test_missing_resources_have_no_iac_item(self, cloud_resources, iac_resources):
        """Resources with State=Missing must have IacResourceItem=None."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Missing":
                assert item.IacResourceItem is None, (
                    f"Expected IacResourceItem=None for Missing resource "
                    f"id={item.CloudResourceItem.get('id')}"
                )

    def test_modified_resources_have_changelog(self, cloud_resources, iac_resources):
        """Resources with State=Modified must have at least one ChangeLog entry."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Modified":
                assert len(item.ChangeLog) > 0, (
                    f"Modified resource id={item.CloudResourceItem.get('id')} "
                    f"has an empty ChangeLog"
                )

    def test_match_resources_have_empty_changelog(self, cloud_resources, iac_resources):
        """Resources with State=Match must have an empty ChangeLog."""
        results = compare_resources(cloud_resources, iac_resources)
        for item in results:
            if item.State == "Match":
                assert item.ChangeLog == [], (
                    f"Match resource id={item.CloudResourceItem.get('id')} "
                    f"has unexpected ChangeLog entries: {item.ChangeLog}"
                )

    # =========================================================================
    # Report Structure Tests
    # =========================================================================

    def test_report_is_generated(self, cloud_resources, iac_resources, tmp_path):
        """Report file must exist and be a flat JSON array (spec requirement)."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        assert output.exists(), "Report file was not created on disk"
        assert isinstance(report, list), (
            f"Report must be a flat list, got {type(report).__name__}"
        )
        assert len(report) == len(cloud_resources), (
            f"Expected {len(cloud_resources)} items in report, got {len(report)}"
        )

    def test_report_items_have_required_keys(self, cloud_resources, iac_resources, tmp_path):
        """Every report item must contain all four required top-level keys."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        required = {"CloudResourceItem", "IacResourceItem", "State", "ChangeLog"}
        for item in report:
            missing_keys = required - item.keys()
            assert not missing_keys, (
                f"Report item is missing keys: {missing_keys}. Found: {set(item.keys())}"
            )

    def test_changelog_entries_use_spec_field_names(
        self, cloud_resources, iac_resources, tmp_path
    ):
        """
        ChangeLog entries must use the spec field names:
            KeyName / CloudValue / IacValue
        and must NOT contain the old snake_case names:
            field / cloud_value / iac_value
        """
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        for item in report:
            for entry in item["ChangeLog"]:
                assert "KeyName"    in entry, f"'KeyName' missing in: {entry}"
                assert "CloudValue" in entry, f"'CloudValue' missing in: {entry}"
                assert "IacValue"   in entry, f"'IacValue' missing in: {entry}"
                # Ensure deprecated names are absent
                assert "field"       not in entry, f"Old key 'field' found in: {entry}"
                assert "cloud_value" not in entry, f"Old key 'cloud_value' found in: {entry}"
                assert "iac_value"   not in entry, f"Old key 'iac_value' found in: {entry}"

    def test_generate_persistent_report(self, cloud_resources, iac_resources):
        """
        Write the final comparison report to reports/ for human inspection.
        This is the report that CI/CD uploads as a build artifact.
        """
        output_path = (
            Path(__file__).parent.parent / "reports" / "comparison_report.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = compare_resources(cloud_resources, iac_resources)
        report  = generate_report(results, str(output_path))

        assert output_path.exists(),              "Report file was not created"
        assert output_path.stat().st_size > 0,    "Report file is empty"
        assert isinstance(report, list),           "Report must be a flat array"
        assert len(report) == len(cloud_resources)

    # =========================================================================
    # Array Comparison Tests
    # =========================================================================

    def test_array_element_difference_detected(self):
        """A differing array element must produce a bracket-notation changelog entry."""
        cloud = [{"id": "r1", "ports": [80, 443]}]
        iac   = [{"id": "r1", "ports": [80, 8080]}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "ports[1]" in keys, f"Expected 'ports[1]' in changelog keys: {keys}"

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "ports[1]")
        assert entry.CloudValue == 443
        assert entry.IacValue   == 8080

    def test_array_length_difference_cloud_longer(self):
        """Extra cloud elements must appear with IacValue=None."""
        cloud = [{"id": "r1", "tags": ["prod", "web", "v2"]}]
        iac   = [{"id": "r1", "tags": ["prod"]}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "tags[1]" in keys, f"Expected 'tags[1]' in: {keys}"
        assert "tags[2]" in keys, f"Expected 'tags[2]' in: {keys}"

        e1 = next(e for e in results[0].ChangeLog if e.KeyName == "tags[1]")
        assert e1.CloudValue == "web"
        assert e1.IacValue   is None

        e2 = next(e for e in results[0].ChangeLog if e.KeyName == "tags[2]")
        assert e2.CloudValue == "v2"
        assert e2.IacValue   is None

    def test_iac_array_longer_than_cloud(self):
        """Extra IaC elements must appear with CloudValue=None."""
        cloud = [{"id": "r1", "zones": ["us-east-1a"]}]
        iac   = [{"id": "r1", "zones": ["us-east-1a", "us-east-1b"]}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "zones[1]" in keys, f"Expected 'zones[1]' in: {keys}"

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "zones[1]")
        assert entry.CloudValue is None
        assert entry.IacValue   == "us-east-1b"

    def test_nested_objects_inside_array(self):
        """Fields inside objects that are array elements use key[i].field notation."""
        cloud = [{"id": "r1", "rules": [{"action": "allow", "port": 80}]}]
        iac   = [{"id": "r1", "rules": [{"action": "deny",  "port": 80}]}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "rules[0].action" in keys, (
            f"Expected 'rules[0].action' in changelog keys: {keys}"
        )

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "rules[0].action")
        assert entry.CloudValue == "allow"
        assert entry.IacValue   == "deny"

    def test_nested_array_inside_array(self):
        """Arrays nested inside arrays must use chained bracket notation key[i][j]."""
        cloud = [{"id": "r1", "matrix": [[1, 2], [3, 4]]}]
        iac   = [{"id": "r1", "matrix": [[1, 2], [3, 9]]}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "matrix[1][1]" in keys, (
            f"Expected 'matrix[1][1]' in changelog keys: {keys}"
        )

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "matrix[1][1]")
        assert entry.CloudValue == 4
        assert entry.IacValue   == 9

    def test_mixed_nested_objects_and_arrays(self):
        """Complex mixed structures produce combined dot + bracket notation keys."""
        cloud = [{"id": "r1", "config": {"listeners": [{"port": 80,  "protocol": "HTTP"}]}}]
        iac   = [{"id": "r1", "config": {"listeners": [{"port": 443, "protocol": "HTTPS"}]}}]

        results = compare_resources(cloud, iac)

        assert results[0].State == "Modified"
        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "config.listeners[0].port"     in keys, f"Key not found in: {keys}"
        assert "config.listeners[0].protocol" in keys, f"Key not found in: {keys}"

    def test_identical_arrays_produce_no_changelog(self):
        """Identical arrays must result in State=Match with an empty ChangeLog."""
        cloud = [{"id": "r1", "ports": [80, 443], "tags": ["prod"]}]
        iac   = [{"id": "r1", "ports": [80, 443], "tags": ["prod"]}]

        results = compare_resources(cloud, iac)

        assert results[0].State   == "Match"
        assert results[0].ChangeLog == []