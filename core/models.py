from dataclasses import dataclass, field
from typing import Optional, List, Literal

# Allowed state values
State = Literal["Missing", "Match", "Modified"]


@dataclass
class ChangeLogEntry:
    KeyName: str        # ✅ Fixed: was 'field'
    CloudValue: object  # ✅ Fixed: was 'cloud_value'
    IacValue: object    # ✅ Fixed: was 'iac_value'


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
                    "KeyName": c.KeyName,
                    "CloudValue": c.CloudValue,
                    "IacValue": c.IacValue
                }
                for c in self.ChangeLog
            ]
        }