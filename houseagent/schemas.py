# ABOUTME: Pydantic models for sensor message validation and transformation
# ABOUTME: Supports new office format and legacy home automation format

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class LegacyMessage(BaseModel):
    """Legacy format - home automation compatibility"""

    sensor: Optional[str] = None
    value: Optional[Any] = None
    room: Optional[str] = None


class SensorMessage(BaseModel):
    """Enhanced format for office sensor messages"""

    ts: str
    sensor_id: str
    sensor_type: str
    zone_id: str
    site_id: str = "hq"
    floor: int = 1
    value: Dict[str, Any]
    quality: Optional[Dict[str, Any]] = None

    @classmethod
    def from_legacy(cls, msg: Dict, zone_map: Dict):
        """Convert legacy message to new format"""
        return cls(
            ts=datetime.now().isoformat(),
            sensor_id=msg.get("sensor", "unknown"),
            sensor_type=msg.get("sensor", "unknown"),
            zone_id=zone_map.get(msg.get("room"), "unknown"),
            value={"reading": msg.get("value")},
        )
