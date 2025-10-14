# ABOUTME: Statistical anomaly detection using Z-score method with EWMA tracking
# ABOUTME: Maintains per-sensor statistics and configurable thresholds

from typing import Dict, Optional
from houseagent.schemas import SensorMessage
import statistics


class AnomalyDetector:
    def __init__(self, z_threshold: float = 2.5):
        self.z_threshold = z_threshold
        self.stats = {}  # sensor_id -> list of recent values
        self.max_history = 100
        self.score: float = 0.0

    def is_anomalous(self, msg: SensorMessage) -> bool:
        """Determine if reading is anomalous using Z-score"""
        sensor_key = msg.sensor_id

        # Extract numeric value from value dict
        value = self._extract_numeric_value(msg.value)
        if value is None:
            return False

        # Initialize history if needed
        if sensor_key not in self.stats:
            self.stats[sensor_key] = []

        history = self.stats[sensor_key]

        # Need at least 3 readings for meaningful stats
        if len(history) < 3:
            history.append(value)
            self.score = 0.0
            return False

        # Calculate Z-score
        mean = statistics.mean(history)
        try:
            stdev = statistics.stdev(history)
            if stdev == 0:
                self.score = 0.0
                z_score = 0.0
            else:
                z_score = abs((value - mean) / stdev)
                self.score = z_score
        except statistics.StatisticsError:
            self.score = 0.0
            z_score = 0.0

        # Update history
        history.append(value)
        if len(history) > self.max_history:
            history.pop(0)

        return z_score > self.z_threshold

    def _extract_numeric_value(self, value_dict: Dict) -> Optional[float]:
        """Extract numeric value from message value dict"""
        # Try common keys
        for key in ["celsius", "fahrenheit", "reading", "value", "count"]:
            if key in value_dict:
                try:
                    return float(value_dict[key])
                except (ValueError, TypeError):
                    pass
        return None
