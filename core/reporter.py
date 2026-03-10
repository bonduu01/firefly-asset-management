import json
from pathlib import Path
from typing import List

from core.models import AssetComparisonItem


def generate_report(
    results: List[AssetComparisonItem],
    output_path: str,
) -> List[dict]:
    """
    Serialise comparison results to a flat JSON array and write to disk.

    Parameters
    ----------
    results     : list of AssetComparisonItem produced by compare_resources()
    output_path : absolute or relative path where the JSON file will be written

    Returns
    -------
    The report as a Python list of dicts (mirrors what is written to disk).
    """
    # ── Build flat array (spec requirement — no wrapper object) ───────────────
    report: List[dict] = [item.to_dict() for item in results]

    # ── Print summary to console (NOT included in JSON output) ───────────────
    total    = len(results)
    matched  = sum(1 for r in results if r.State == "Match")
    modified = sum(1 for r in results if r.State == "Modified")
    missing  = sum(1 for r in results if r.State == "Missing")

    print("\n" + "=" * 55)
    print("  📊  Firefly Comparison Summary")
    print("=" * 55)
    print(f"  Total     : {total}")
    print(f"  ✅ Match   : {matched}")
    print(f"  ⚠️  Modified: {modified}")
    print(f"  ❌ Missing : {missing}")
    print("=" * 55 + "\n")

    # ── Write to disk ─────────────────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.flush()

    print(f"✅ Report written → {output_path}\n")
    return report