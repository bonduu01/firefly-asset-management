import json
from typing import List
from pathlib import Path
from core.models import AssetComparisonItem


def generate_report(results: List[AssetComparisonItem], output_path: str) -> List[dict]:
    # ✅ Fixed: flat array — spec requires NO wrapper object with 'summary'/'results' keys
    report = [item.to_dict() for item in results]

    # Summary printed to console only — NOT included in JSON output
    total = len(results)
    match = sum(1 for r in results if r.State == "Match")
    modified = sum(1 for r in results if r.State == "Modified")
    missing = sum(1 for r in results if r.State == "Missing")
    print(f"\n📊 Summary: {total} total | {match} match | {modified} modified | {missing} missing\n")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.flush()

    print(f"✅ Report written to: {output_path}")
    return report