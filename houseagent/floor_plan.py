# ABOUTME: Floor plan model for spatial reasoning and zone relationships
# ABOUTME: Supports adjacency queries, camera FOV overlaps, and sensor locations

import json
from typing import List, Dict
from pathlib import Path


class FloorPlanModel:
    def __init__(self, config_path: str = "config/floor_plan.json"):
        self.zones: Dict[str, Dict] = {}
        self.sensors: Dict[str, Dict] = {}
        self.cameras: List[Dict] = []
        self.adjacency: Dict[str, List[str]] = {}

        if Path(config_path).exists():
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load floor plan configuration from JSON"""
        with open(config_path, "r") as f:
            config = json.load(f)

        self.zones = config.get("zones", {})
        self.sensors = config.get("sensors", {})
        self.cameras = config.get("cameras", [])
        self.adjacency = config.get("adjacency", {})

    def get_adjacent_zones(self, zone_id: str) -> List[str]:
        """Get zones adjacent to given zone"""
        return self.adjacency.get(zone_id, [])

    @classmethod
    def load(cls, config_path: str = "config/floor_plan.json") -> "FloorPlanModel":
        """Factory method to load floor plan"""
        return cls(config_path)
