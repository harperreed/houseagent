# ABOUTME: Situation builder for clustering messages into spatial/temporal situations
# ABOUTME: Implements corroboration logic and confidence scoring

from typing import List, Dict, Optional
from collections import Counter
from dataclasses import dataclass
from ulid import ULID


@dataclass
class Situation:
    """Represents a clustered situation from multiple sensor readings"""

    id: str
    messages: List[Dict]
    features: Dict
    confidence: float

    def requires_response(self) -> bool:
        """Determine if situation requires AI response"""
        # Require response if multiple sensors in same zone
        return len(self.messages) >= 2

    def to_prompt_json(self) -> Dict:
        """Convert situation to JSON for AI prompt"""
        return {
            "id": self.id,
            "message_count": len(self.messages),
            "zones": self.features.get("zones", []),
            "event_counts": self.features.get("event_counts", {}),
            "confidence": self.confidence,
            "messages": self.messages,
        }


class SituationBuilder:
    def __init__(self):
        pass

    def build(self, messages: List[Dict], floor_plan) -> Optional[Situation]:
        """Build situation from message batch"""
        if not messages:
            return None

        # Cluster by zone
        zone_clusters = self._cluster_by_zone(messages)

        # Compute features
        features = {
            "event_counts": dict(Counter([m.get("sensor_type") for m in messages])),
            "zones": list(zone_clusters.keys()),
            "anomaly_scores": [
                m.get("value", {}).get("anomaly_score", 0) for m in messages
            ],
        }

        # Check for corroboration (2+ sensors)
        if self._has_corroboration(messages):
            return Situation(
                id=f"sit-{ULID()}", messages=messages, features=features, confidence=0.8
            )

        return None

    def _cluster_by_zone(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster messages by zone_id"""
        clusters = {}
        for msg in messages:
            zone_id = msg.get("zone_id", "unknown")
            if zone_id not in clusters:
                clusters[zone_id] = []
            clusters[zone_id].append(msg)
        return clusters

    def _has_corroboration(self, messages: List[Dict]) -> bool:
        """Check if multiple sensors corroborate situation"""
        unique_sensors = set(m.get("sensor_id") for m in messages)
        return len(unique_sensors) >= 2
