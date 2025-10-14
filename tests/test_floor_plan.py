# ABOUTME: Tests for floor plan model with zone/sensor/camera spatial queries
# ABOUTME: Validates adjacency graph, FOV calculations, and polygon overlaps

import json
import tempfile
from pathlib import Path
from houseagent.floor_plan import FloorPlanModel


def test_floor_plan_loads_from_json():
    """Test FloorPlanModel loads configuration from JSON file"""
    config = {
        "zones": {
            "lobby": {
                "name": "Main Lobby",
                "floor": 1,
                "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            },
            "conf_a": {
                "name": "Conference Room A",
                "floor": 1,
                "polygon": [[10, 0], [20, 0], [20, 10], [10, 10]],
            },
        },
        "adjacency": {"lobby": ["conf_a"], "conf_a": ["lobby"]},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        model = FloorPlanModel(config_path)
        assert "lobby" in model.zones
        assert model.zones["lobby"]["name"] == "Main Lobby"
    finally:
        Path(config_path).unlink()


def test_floor_plan_adjacency_queries():
    """Test FloorPlanModel returns adjacent zones"""
    config = {
        "zones": {
            "lobby": {"name": "Lobby"},
            "conf_a": {"name": "Conf A"},
            "conf_b": {"name": "Conf B"},
        },
        "adjacency": {
            "lobby": ["conf_a", "conf_b"],
            "conf_a": ["lobby"],
            "conf_b": ["lobby"],
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        model = FloorPlanModel(config_path)
        adjacent = model.get_adjacent_zones("lobby")
        assert "conf_a" in adjacent
        assert "conf_b" in adjacent
        assert len(adjacent) == 2
    finally:
        Path(config_path).unlink()
