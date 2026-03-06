import json
import pytest
from pathlib import Path
from core.comparator import compare_resources
from core.reporter import generate_report


class TestFireflyAssetManagement:

    # ── Existing tests (spec-compliance fixes applied) ─────────────────────

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
        """Report file must exist and be a flat JSON array (spec requirement)."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        assert output.exists()
        assert isinstance(report, list), "Report must be a flat list, not a dict"
        assert len(report) == len(cloud_resources)

    def test_report_items_have_required_keys(self, cloud_resources, iac_resources, tmp_path):
        """Each report item must have CloudResourceItem, IacResourceItem, State, ChangeLog."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        required_keys = {"CloudResourceItem", "IacResourceItem", "State", "ChangeLog"}
        for item in report:
            assert required_keys.issubset(item.keys()), (
                f"Report item missing keys. Found: {item.keys()}"
            )

    def test_changelog_entries_use_spec_field_names(self, cloud_resources, iac_resources, tmp_path):
        """ChangeLog entries must use KeyName/CloudValue/IacValue (not field/cloud_value/iac_value)."""
        results = compare_resources(cloud_resources, iac_resources)
        output = tmp_path / "comparison_report.json"
        report = generate_report(results, str(output))

        for item in report:
            for entry in item["ChangeLog"]:
                assert "KeyName" in entry,    f"Missing 'KeyName' in changelog entry: {entry}"
                assert "CloudValue" in entry, f"Missing 'CloudValue' in changelog entry: {entry}"
                assert "IacValue" in entry,   f"Missing 'IacValue' in changelog entry: {entry}"
                # Ensure old wrong names are NOT present
                assert "field" not in entry,       "Old key 'field' found — should be 'KeyName'"
                assert "cloud_value" not in entry, "Old key 'cloud_value' found — should be 'CloudValue'"
                assert "iac_value" not in entry,   "Old key 'iac_value' found — should be 'IacValue'"

    def test_generate_persistent_report(self, cloud_resources, iac_resources):
        """Writes the final comparison report to reports/ directory for human inspection."""
        output_path = Path(__file__).parent.parent / "reports" / "comparison_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = compare_resources(cloud_resources, iac_resources)
        report = generate_report(results, str(output_path))

        assert output_path.exists(), "Report file was not created"
        assert output_path.stat().st_size > 0, "Report file is empty"
        assert isinstance(report, list), "Persistent report must be a flat array"

    # ── New: Array comparison tests ────────────────────────────────────────

    def test_array_element_difference_detected(self):
        """Array elements that differ must produce bracket-notation changelog entries."""
        cloud = [{"id": "r1", "ports": [80, 443]}]
        iac   = [{"id": "r1", "ports": [80, 8080]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "ports[1]" in keys, f"Expected 'ports[1]' in changelog keys, got: {keys}"

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "ports[1]")
        assert entry.CloudValue == 443
        assert entry.IacValue == 8080

    def test_array_length_difference_detected(self):
        """Extra elements in either array must each produce their own changelog entry."""
        cloud = [{"id": "r1", "tags": ["prod", "web", "v2"]}]
        iac   = [{"id": "r1", "tags": ["prod"]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        # Cloud has 2 extra elements: tags[1] and tags[2]
        assert "tags[1]" in keys, f"Expected 'tags[1]' in: {keys}"
        assert "tags[2]" in keys, f"Expected 'tags[2]' in: {keys}"

        entry_1 = next(e for e in results[0].ChangeLog if e.KeyName == "tags[1]")
        assert entry_1.CloudValue == "web"
        assert entry_1.IacValue is None

        entry_2 = next(e for e in results[0].ChangeLog if e.KeyName == "tags[2]")
        assert entry_2.CloudValue == "v2"
        assert entry_2.IacValue is None

    def test_iac_array_longer_than_cloud(self):
        """IaC array with more elements must show CloudValue=None for the extras."""
        cloud = [{"id": "r1", "zones": ["us-east-1a"]}]
        iac   = [{"id": "r1", "zones": ["us-east-1a", "us-east-1b"]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "zones[1]" in keys

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "zones[1]")
        assert entry.CloudValue is None
        assert entry.IacValue == "us-east-1b"

    def test_nested_objects_inside_array(self):
        """Diffs inside objects that are elements of an array use combined notation."""
        cloud = [{"id": "r1", "rules": [{"action": "allow", "port": 80}]}]
        iac   = [{"id": "r1", "rules": [{"action": "deny",  "port": 80}]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        # Nested object field inside array: rules[0].action
        assert "rules[0].action" in keys, f"Expected 'rules[0].action' in: {keys}"

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "rules[0].action")
        assert entry.CloudValue == "allow"
        assert entry.IacValue == "deny"

    def test_nested_array_inside_array(self):
        """Arrays nested inside arrays must use chained bracket-notation."""
        cloud = [{"id": "r1", "matrix": [[1, 2], [3, 4]]}]
        iac   = [{"id": "r1", "matrix": [[1, 2], [3, 9]]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "matrix[1][1]" in keys, f"Expected 'matrix[1][1]' in: {keys}"

        entry = next(e for e in results[0].ChangeLog if e.KeyName == "matrix[1][1]")
        assert entry.CloudValue == 4
        assert entry.IacValue == 9

    def test_mixed_nested_objects_and_arrays(self):
        """Complex mixed structures with both nested dicts and arrays are diffed correctly."""
        cloud = [{"id": "r1", "config": {"listeners": [{"port": 80, "protocol": "HTTP"}]}}]
        iac   = [{"id": "r1", "config": {"listeners": [{"port": 443, "protocol": "HTTPS"}]}}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Modified"

        keys = [e.KeyName for e in results[0].ChangeLog]
        assert "config.listeners[0].port" in keys,     f"Expected key not found in: {keys}"
        assert "config.listeners[0].protocol" in keys, f"Expected key not found in: {keys}"

    def test_identical_arrays_produce_no_changelog(self):
        """Arrays that are identical must not produce any changelog entries."""
        cloud = [{"id": "r1", "ports": [80, 443], "tags": ["prod"]}]
        iac   = [{"id": "r1", "ports": [80, 443], "tags": ["prod"]}]

        results = compare_resources(cloud, iac)
        assert results[0].State == "Match"
        assert results[0].ChangeLog == []