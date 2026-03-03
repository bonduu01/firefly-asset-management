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
    Supports nested fields using dot-notation (e.g. 'tags.env').
    """
    changes = []
    all_keys = set(cloud.keys()) | set(iac.keys())

    for key in all_keys:
        full_key = f"{prefix}{key}"
        cloud_val = cloud.get(key)
        iac_val = iac.get(key)

        if isinstance(cloud_val, dict) and isinstance(iac_val, dict):
            # Recurse into nested objects
            changes.extend(_diff_resources(cloud_val, iac_val, prefix=f"{full_key}."))
        elif cloud_val != iac_val:
            changes.append(ChangeLogEntry(
                field=full_key,
                cloud_value=cloud_val,
                iac_value=iac_val
            ))

    return changes