from typing import List, Dict, Any
from core.models import AssetComparisonItem, ChangeLogEntry


def compare_resources(
    cloud_resources: List[Dict[str, Any]],
    iac_resources: List[Dict[str, Any]]
) -> List[AssetComparisonItem]:
    """
    Compare cloud resources against IaC resources.
    Match is done by 'id' field.
    Returns a list of AssetComparisonItem results.
    """
    # Index IaC resources by their ID for O(1) lookup
    iac_index: Dict[str, Dict] = {
        r["id"]: r for r in iac_resources if "id" in r
    }

    results = []

    for cloud_resource in cloud_resources:
        resource_id = cloud_resource.get("id")
        iac_resource = iac_index.get(resource_id)

        if iac_resource is None:
            # No matching IaC resource found → Missing
            results.append(AssetComparisonItem(
                CloudResourceItem=cloud_resource,
                IacResourceItem=None,
                State="Missing",
                ChangeLog=[]
            ))
        else:
            # Check for field-level differences
            changelog = _diff_resources(cloud_resource, iac_resource)
            state = "Match" if not changelog else "Modified"

            results.append(AssetComparisonItem(
                CloudResourceItem=cloud_resource,
                IacResourceItem=iac_resource,
                State=state,
                ChangeLog=changelog
            ))

    return results


def _diff_resources(
    cloud: Dict[str, Any],
    iac: Dict[str, Any],
    prefix: str = ""
) -> List[ChangeLogEntry]:
    """
    Recursively diff two dicts and return a list of ChangeLogEntry.
    Supports:
      - Nested objects via dot-notation  (e.g. 'tags.env')
      - Arrays via bracket-notation      (e.g. 'ports[0]')
      - Mixed nested objects inside arrays (e.g. 'rules[0].action')
    """
    changes = []
    all_keys = set(cloud.keys()) | set(iac.keys())

    for key in all_keys:
        full_key = f"{prefix}{key}"
        cloud_val = cloud.get(key)
        iac_val = iac.get(key)

        if isinstance(cloud_val, dict) and isinstance(iac_val, dict):
            # ── Recurse into nested dicts ──────────────────────────────────
            changes.extend(_diff_resources(cloud_val, iac_val, prefix=f"{full_key}."))

        elif isinstance(cloud_val, list) and isinstance(iac_val, list):
            # ✅ Fixed: recurse into arrays with bracket-notation keys
            changes.extend(_diff_arrays(cloud_val, iac_val, full_key))

        elif isinstance(cloud_val, list) and iac_val is None:
            # Array exists in cloud but missing entirely in IaC
            for i, item in enumerate(cloud_val):
                changes.append(ChangeLogEntry(
                    KeyName=f"{full_key}[{i}]",
                    CloudValue=item,
                    IacValue=None
                ))

        elif cloud_val is None and isinstance(iac_val, list):
            # Array exists in IaC but missing entirely in cloud
            for i, item in enumerate(iac_val):
                changes.append(ChangeLogEntry(
                    KeyName=f"{full_key}[{i}]",
                    CloudValue=None,
                    IacValue=item
                ))

        elif cloud_val != iac_val:
            # ── Scalar or type mismatch ────────────────────────────────────
            changes.append(ChangeLogEntry(
                KeyName=full_key,
                CloudValue=cloud_val,
                IacValue=iac_val
            ))

    return changes


def _diff_arrays(
    cloud_arr: List[Any],
    iac_arr: List[Any],
    key_prefix: str
) -> List[ChangeLogEntry]:
    """
    Compare two lists element-by-element.
    Uses bracket-notation for keys: key_prefix[0], key_prefix[1], etc.
    Handles:
      - Different array lengths
      - Nested dicts inside arrays
      - Nested arrays inside arrays
      - Scalar value differences
    """
    changes = []
    max_len = max(len(cloud_arr), len(iac_arr))

    for i in range(max_len):
        array_key = f"{key_prefix}[{i}]"

        if i >= len(cloud_arr):
            # IaC has more elements than cloud
            changes.append(ChangeLogEntry(
                KeyName=array_key,
                CloudValue=None,
                IacValue=iac_arr[i]
            ))
        elif i >= len(iac_arr):
            # Cloud has more elements than IaC
            changes.append(ChangeLogEntry(
                KeyName=array_key,
                CloudValue=cloud_arr[i],
                IacValue=None
            ))
        else:
            cloud_item = cloud_arr[i]
            iac_item = iac_arr[i]

            if isinstance(cloud_item, dict) and isinstance(iac_item, dict):
                # Recurse into nested object inside array
                changes.extend(_diff_resources(cloud_item, iac_item, prefix=f"{array_key}."))

            elif isinstance(cloud_item, list) and isinstance(iac_item, list):
                # Recurse into nested array inside array
                changes.extend(_diff_arrays(cloud_item, iac_item, array_key))

            elif cloud_item != iac_item:
                changes.append(ChangeLogEntry(
                    KeyName=array_key,
                    CloudValue=cloud_item,
                    IacValue=iac_item
                ))

    return changes