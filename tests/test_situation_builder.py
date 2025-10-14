# ABOUTME: Tests for situation builder clustering messages into coherent situations
# ABOUTME: Validates zone clustering, corroboration, and confidence scoring

from houseagent.situation_builder import SituationBuilder
from houseagent.floor_plan import FloorPlanModel
import tempfile
import json


def test_situation_builder_creates_situation_from_messages():
    """Test SituationBuilder clusters messages into situation"""
    # Create floor plan
    config = {"zones": {"lobby": {"name": "Lobby"}}, "adjacency": {"lobby": []}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        f.flush()
        config_path = f.name

    floor_plan = FloorPlanModel(config_path)
    builder = SituationBuilder()

    messages = [
        {
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "motion_01",
            "sensor_type": "motion",
            "zone_id": "lobby",
            "value": {"detected": True},
        },
        {
            "ts": "2025-10-14T10:30:05Z",
            "sensor_id": "temp_01",
            "sensor_type": "temperature",
            "zone_id": "lobby",
            "value": {"celsius": 22.0},
        },
    ]

    situation = builder.build(messages, floor_plan)

    assert situation is not None
    assert len(situation.messages) == 2
    assert "lobby" in situation.features["zones"]


def test_situation_builder_requires_corroboration():
    """Test SituationBuilder requires 2+ sensors for situation"""
    config = {"zones": {"lobby": {}}, "adjacency": {}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        f.flush()
        config_path = f.name

    floor_plan = FloorPlanModel(config_path)
    builder = SituationBuilder()

    # Single sensor - no situation
    single_message = [
        {
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "motion_01",
            "sensor_type": "motion",
            "zone_id": "lobby",
            "value": {"detected": True},
        }
    ]

    situation = builder.build(single_message, floor_plan)
    assert situation is None
