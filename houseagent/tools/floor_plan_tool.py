# ABOUTME: Floor plan tool for spatial queries about zones and sensors
# ABOUTME: Provides adjacency lookups, zone info, and camera placement data

from typing import Dict, Any
from houseagent.floor_plan import FloorPlanModel


class FloorPlanTool:
    def __init__(self, floor_plan: FloorPlanModel):
        self.floor_plan = floor_plan

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute floor plan query"""
        query = params.get("query")

        if query == "adjacent_zones":
            zone_id = params.get("zone_id")
            if not zone_id:
                return {"error": "zone_id required"}

            adjacent = self.floor_plan.get_adjacent_zones(zone_id)
            return {"zones": adjacent}

        elif query == "zone_info":
            zone_id = params.get("zone_id")
            if not zone_id:
                return {"error": "zone_id required"}

            zone_info = self.floor_plan.zones.get(zone_id)
            if not zone_info:
                return {"error": "Zone not found"}

            return {"zone": zone_info}

        else:
            return {"error": "Unknown query type"}

    def get_description(self) -> str:
        """Tool description for AI"""
        zones = list(self.floor_plan.zones.keys())
        return f"""Query floor plan spatial information.

        Available zones: {", ".join(zones)}

        Usage:
        - floor_plan_query(query="adjacent_zones", zone_id="hack_area") - get zones adjacent to specified zone
        - floor_plan_query(query="zone_info", zone_id="hack_area") - get full zone information including sensors

        Returns zone data from floor plan configuration."""
