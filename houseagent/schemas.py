# ABOUTME: Pydantic models for sensor message validation and transformation
# ABOUTME: Supports new office format and legacy home automation format

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class LegacyMessage(BaseModel):
    """Legacy format - home automation compatibility"""

    # Old format fields
    sensor: Optional[str] = None
    value: Optional[Any] = None
    room: Optional[str] = None

    # Home Assistant format fields
    entity_id: Optional[str] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    area: Optional[str] = None
    timestamp: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


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
        """Convert legacy message to new format (handles both old and Home Assistant formats)"""
        # Home Assistant format
        if "entity_id" in msg:
            # Extract sensor type from entity_id (e.g., "binary_sensor.speaking_detected" -> "speaking")
            entity_parts = msg.get("entity_id", "").split(".")
            sensor_type = (
                entity_parts[-1].replace("_detected", "").replace("_", " ")
                if len(entity_parts) > 1
                else "unknown"
            )

            return cls(
                ts=msg.get("timestamp", datetime.now().isoformat()),
                sensor_id=msg.get("entity_id", "unknown"),
                sensor_type=sensor_type,
                zone_id=zone_map.get(msg.get("area"), msg.get("area", "unknown")),
                value={
                    "state": msg.get("to_state"),
                    "previous_state": msg.get("from_state"),
                    "attributes": msg.get("attributes", {}),
                },
            )

        # Old format
        return cls(
            ts=datetime.now().isoformat(),
            sensor_id=msg.get("sensor", "unknown"),
            sensor_type=msg.get("sensor", "unknown"),
            zone_id=zone_map.get(msg.get("room"), "unknown"),
            value={"reading": msg.get("value")},
        )
