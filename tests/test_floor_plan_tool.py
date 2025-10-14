# ABOUTME: Tests for floor plan tool providing spatial query capabilities
# ABOUTME: Validates zone queries, adjacency lookups, and camera placement

import json
import tempfile
from pathlib import Path
from houseagent.tools.floor_plan_tool import FloorPlanTool
from houseagent.floor_plan import FloorPlanModel


def test_floor_plan_tool_queries_adjacent_zones():
    """Test FloorPlanTool returns adjacent zones"""
    config = {
        "zones": {"lobby": {"name": "Lobby"}, "conf_a": {"name": "Conf A"}},
        "adjacency": {"lobby": ["conf_a"], "conf_a": ["lobby"]},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        floor_plan = FloorPlanModel(config_path)
        tool = FloorPlanTool(floor_plan)
        result = tool.execute({"query": "adjacent_zones", "zone_id": "lobby"})

        assert "zones" in result
        assert "conf_a" in result["zones"]
    finally:
        Path(config_path).unlink()


def test_floor_plan_tool_returns_zone_info():
    """Test FloorPlanTool returns zone details"""
    config = {"zones": {"lobby": {"name": "Main Lobby", "floor": 1}}, "adjacency": {}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        floor_plan = FloorPlanModel(config_path)
        tool = FloorPlanTool(floor_plan)
        result = tool.execute({"query": "zone_info", "zone_id": "lobby"})

        assert "zone" in result
        assert result["zone"]["name"] == "Main Lobby"
        assert result["zone"]["floor"] == 1
    finally:
        Path(config_path).unlink()


def test_floor_plan_tool_handles_missing_zone_id():
    """Test FloorPlanTool returns error for missing zone_id parameter"""
    config = {"zones": {"lobby": {"name": "Lobby"}}, "adjacency": {}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        floor_plan = FloorPlanModel(config_path)
        tool = FloorPlanTool(floor_plan)

        # Test adjacent_zones without zone_id
        result = tool.execute({"query": "adjacent_zones"})
        assert "error" in result
        assert result["error"] == "zone_id required"

        # Test zone_info without zone_id
        result = tool.execute({"query": "zone_info"})
        assert "error" in result
        assert result["error"] == "zone_id required"
    finally:
        Path(config_path).unlink()


def test_floor_plan_tool_handles_unknown_zone():
    """Test FloorPlanTool returns error for unknown zone"""
    config = {"zones": {"lobby": {"name": "Lobby"}}, "adjacency": {}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        floor_plan = FloorPlanModel(config_path)
        tool = FloorPlanTool(floor_plan)
        result = tool.execute({"query": "zone_info", "zone_id": "nonexistent"})

        assert "error" in result
        assert result["error"] == "Zone not found"
    finally:
        Path(config_path).unlink()


def test_floor_plan_tool_handles_unknown_query():
    """Test FloorPlanTool returns error for unknown query type"""
    config = {"zones": {"lobby": {"name": "Lobby"}}, "adjacency": {}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        floor_plan = FloorPlanModel(config_path)
        tool = FloorPlanTool(floor_plan)
        result = tool.execute({"query": "invalid_query", "zone_id": "lobby"})

        assert "error" in result
        assert result["error"] == "Unknown query type"
    finally:
        Path(config_path).unlink()
