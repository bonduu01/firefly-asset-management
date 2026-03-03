import json
from typing import List
from pathlib import Path
from core.models import AssetComparisonItem

BASE_DIR = Path(__file__).parent.parent

def generate_report(results: List[AssetComparisonItem], output_path: str) -> dict:
    report = {
        "summary": {
            "total": len(results),
            "match": sum(1 for r in results if r.State == "Match"),
            "modified": sum(1 for r in results if r.State == "Modified"),
            "missing": sum(1 for r in results if r.State == "Missing"),
        },
        "results": [item.to_dict() for item in results]
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.flush()  # ← Force flush buffer to disk immediately

    return report