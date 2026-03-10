from dataclasses import dataclass, field
from typing import Optional, List, Literal

# The three allowed drift states
State = Literal["Missing", "Match", "Modified"]


@dataclass
class ChangeLogEntry:
    """
    Represents a single field-level difference between a cloud resource
    and its IaC counterpart.

    Field names are exactly as required by the specification:
        KeyName     — dot/bracket-notation path  (e.g. "size", "tags.env", "ports[1]")
        CloudValue  — value found in the live cloud resource  (None if absent)
        IacValue    — value declared in IaC                   (None if absent)
    """
    KeyName: str
    CloudValue: object
    IacValue: object


@dataclass
class AssetComparisonItem:
    """
    Represents the full comparison result for one cloud resource.

    CloudResourceItem — the original cloud resource dict
    IacResourceItem   — the matching IaC resource dict, or None if missing
    State             — "Match" | "Modified" | "Missing"
    ChangeLog         — list of ChangeLogEntry (non-empty only when State == "Modified")
    """
    CloudResourceItem: dict
    IacResourceItem: Optional[dict]
    State: State
    ChangeLog: List[ChangeLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a plain dict matching the JSON report specification."""
        return {
            "CloudResourceItem": self.CloudResourceItem,
            "IacResourceItem": self.IacResourceItem,
            "State": self.State,
            "ChangeLog": [
                {
                    "KeyName": entry.KeyName,
                    "CloudValue": entry.CloudValue,
                    "IacValue": entry.IacValue,
                }
                for entry in self.ChangeLog
            ],
        }