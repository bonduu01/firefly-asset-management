from typing import List, Dict, Any
from core.models import AssetComparisonItem, ChangeLogEntry


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compare_resources(
    cloud_resources: List[Dict[str, Any]],
    iac_resources: List[Dict[str, Any]],
) -> List[AssetComparisonItem]:
    """
    Compare a list of cloud resources against a list of IaC resources.

    Matching is performed by the 'id' field. Each cloud resource receives
    exactly one AssetComparisonItem in the returned list.

    States assigned:
        Missing  — no IaC resource found with the same id
        Match    — IaC resource found and all fields are identical
        Modified — IaC resource found but one or more fields differ
    """
    # Build an O(1) lookup index keyed by resource id
    iac_index: Dict[str, Dict] = {
        r["id"]: r for r in iac_resources if "id" in r
    }

    results: List[AssetComparisonItem] = []

    for cloud_resource in cloud_resources:
        resource_id = cloud_resource.get("id")
        iac_resource = iac_index.get(resource_id)

        if iac_resource is None:
            # ── Missing ──────────────────────────────────────────────────────
            results.append(
                AssetComparisonItem(
                    CloudResourceItem=cloud_resource,
                    IacResourceItem=None,
                    State="Missing",
                    ChangeLog=[],
                )
            )
        else:
            # ── Match or Modified ────────────────────────────────────────────
            changelog = _diff_resources(cloud_resource, iac_resource)
            state: str = "Match" if not changelog else "Modified"

            results.append(
                AssetComparisonItem(
                    CloudResourceItem=cloud_resource,
                    IacResourceItem=iac_resource,
                    State=state,
                    ChangeLog=changelog,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Internal diff helpers
# ---------------------------------------------------------------------------

def _diff_resources(
    cloud: Dict[str, Any],
    iac: Dict[str, Any],
    prefix: str = "",
) -> List[ChangeLogEntry]:
    """
    Recursively diff two dicts and return a list of ChangeLogEntry objects.

    Handles:
      - Scalar fields        → direct equality check
      - Nested dicts         → recursive call with dot-notation prefix
      - Lists / arrays       → delegated to _diff_arrays()
      - One-sided lists      → each element logged individually
    """
    changes: List[ChangeLogEntry] = []
    all_keys = set(cloud.keys()) | set(iac.keys())

    for key in sorted(all_keys):          # sorted for deterministic output
        full_key = f"{prefix}{key}"
        cloud_val = cloud.get(key)
        iac_val = iac.get(key)

        if isinstance(cloud_val, dict) and isinstance(iac_val, dict):
            # Both sides are dicts — recurse
            changes.extend(
                _diff_resources(cloud_val, iac_val, prefix=f"{full_key}.")
            )

        elif isinstance(cloud_val, list) and isinstance(iac_val, list):
            # Both sides are lists — element-by-element diff
            changes.extend(_diff_arrays(cloud_val, iac_val, full_key))

        elif isinstance(cloud_val, list) and iac_val is None:
            # List present in cloud, absent in IaC
            for i, item in enumerate(cloud_val):
                changes.append(
                    ChangeLogEntry(
                        KeyName=f"{full_key}[{i}]",
                        CloudValue=item,
                        IacValue=None,
                    )
                )

        elif cloud_val is None and isinstance(iac_val, list):
            # List present in IaC, absent in cloud
            for i, item in enumerate(iac_val):
                changes.append(
                    ChangeLogEntry(
                        KeyName=f"{full_key}[{i}]",
                        CloudValue=None,
                        IacValue=item,
                    )
                )

        elif cloud_val != iac_val:
            # Scalar mismatch or type mismatch
            changes.append(
                ChangeLogEntry(
                    KeyName=full_key,
                    CloudValue=cloud_val,
                    IacValue=iac_val,
                )
            )

    return changes


def _diff_arrays(
    cloud_arr: List[Any],
    iac_arr: List[Any],
    key_prefix: str,
) -> List[ChangeLogEntry]:
    """
    Compare two lists element-by-element using bracket-notation keys.

    Handles:
      - Different lengths          → missing side logged as None
      - Elements that are dicts    → recurse via _diff_resources()
      - Elements that are lists    → recurse via _diff_arrays()
      - Scalar element mismatch    → direct ChangeLogEntry
    """
    changes: List[ChangeLogEntry] = []
    max_len = max(len(cloud_arr), len(iac_arr))

    for i in range(max_len):
        array_key = f"{key_prefix}[{i}]"

        if i >= len(cloud_arr):
            # IaC array is longer
            changes.append(
                ChangeLogEntry(KeyName=array_key, CloudValue=None, IacValue=iac_arr[i])
            )
            continue

        if i >= len(iac_arr):
            # Cloud array is longer
            changes.append(
                ChangeLogEntry(KeyName=array_key, CloudValue=cloud_arr[i], IacValue=None)
            )
            continue

        cloud_item = cloud_arr[i]
        iac_item = iac_arr[i]

        if isinstance(cloud_item, dict) and isinstance(iac_item, dict):
            # Nested object inside array — recurse with "key[i]." prefix
            changes.extend(
                _diff_resources(cloud_item, iac_item, prefix=f"{array_key}.")
            )

        elif isinstance(cloud_item, list) and isinstance(iac_item, list):
            # Nested array inside array — recurse with "key[i]" prefix
            changes.extend(_diff_arrays(cloud_item, iac_item, array_key))

        elif cloud_item != iac_item:
            changes.append(
                ChangeLogEntry(
                    KeyName=array_key,
                    CloudValue=cloud_item,
                    IacValue=iac_item,
                )
            )

    return changes