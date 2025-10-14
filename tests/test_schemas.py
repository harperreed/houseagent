# ABOUTME: Tests for Pydantic schema models validating sensor messages
# ABOUTME: Covers SensorMessage, LegacyMessage, and format conversions

import pytest
from houseagent.schemas import SensorMessage, LegacyMessage


def test_sensor_message_valid():
    """Test SensorMessage accepts valid office sensor data"""
    msg = SensorMessage(
        ts="2025-10-14T10:30:00Z",
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="conf_room_a",
        site_id="hq",
        floor=1,
        value={"celsius": 22.5},
    )
    assert msg.sensor_id == "temp_01"
    assert msg.value["celsius"] == 22.5


def test_sensor_message_requires_fields():
    """Test SensorMessage rejects missing required fields"""
    with pytest.raises(ValueError):
        SensorMessage(
            sensor_id="temp_01",
            sensor_type="temperature",
            # Missing required fields
        )


def test_legacy_message_format():
    """Test LegacyMessage supports old home automation format"""
    msg = LegacyMessage(sensor="motion_sensor", value=True, room="living_room")
    assert msg.sensor == "motion_sensor"
    assert msg.room == "living_room"


def test_legacy_to_sensor_conversion():
    """Test converting legacy format to new SensorMessage"""
    legacy = {"sensor": "temp_hall", "value": 21.0, "room": "hallway"}
    zone_map = {"hallway": "zone_hall"}

    msg = SensorMessage.from_legacy(legacy, zone_map)
    assert msg.sensor_id == "temp_hall"
    assert msg.zone_id == "zone_hall"
    assert msg.value["reading"] == 21.0


def test_home_assistant_format():
    """Test LegacyMessage supports Home Assistant format"""
    msg = LegacyMessage(
        entity_id="binary_sensor.speaking_detected",
        from_state="off",
        to_state="on",
        area="main_office",
        timestamp="2025-10-14T14:49:00.989588-05:00",
        attributes={"device_class": "occupancy", "friendly_name": "Speaking Detected"},
    )
    assert msg.entity_id == "binary_sensor.speaking_detected"
    assert msg.area == "main_office"
    assert msg.to_state == "on"


def test_home_assistant_to_sensor_conversion():
    """Test converting Home Assistant format to SensorMessage"""
    ha_msg = {
        "entity_id": "binary_sensor.speaking_detected",
        "from_state": "off",
        "to_state": "on",
        "area": "main_office",
        "timestamp": "2025-10-14T14:49:00.989588-05:00",
        "attributes": {
            "device_class": "occupancy",
            "friendly_name": "Speaking Detected",
        },
    }
    zone_map = {"main_office": "office_main"}

    msg = SensorMessage.from_legacy(ha_msg, zone_map)
    assert msg.sensor_id == "binary_sensor.speaking_detected"
    assert msg.sensor_type == "speaking"
    assert msg.zone_id == "office_main"
    assert msg.ts == "2025-10-14T14:49:00.989588-05:00"
    assert msg.value["state"] == "on"
    assert msg.value["previous_state"] == "off"
    assert msg.value["attributes"]["device_class"] == "occupancy"
