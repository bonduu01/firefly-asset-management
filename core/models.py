from dataclasses import dataclass, field
from typing import Optional, List, Literal

# Allowed state values
State = Literal["Missing", "Match", "Modified"]

@dataclass
class ChangeLogEntry:
    field: str
    cloud_value: object
    iac_value: object

@dataclass
class AssetComparisonItem:
    CloudResourceItem: dict
    IacResourceItem: Optional[dict]
    State: State
    ChangeLog: List[ChangeLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "CloudResourceItem": self.CloudResourceItem,
            "IacResourceItem": self.IacResourceItem,
            "State": self.State,
            "ChangeLog": [
                {
                    "field": c.field,
                    "cloud_value": c.cloud_value,
                    "iac_value": c.iac_value
                }
                for c in self.ChangeLog
            ]
        }