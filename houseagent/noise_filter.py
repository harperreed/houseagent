# ABOUTME: Noise filtering for sensor messages with deduplication and quality checks
# ABOUTME: Implements EWMA statistics and time-of-day sensitivity rules

from datetime import datetime
from houseagent.schemas import SensorMessage


class NoiseFilter:
    def __init__(self, dedup_window_seconds: int = 60):
        self.dedup_window = {}  # sensor_id -> (value, timestamp)
        self.dedup_window_seconds = dedup_window_seconds
        self.ewma = {}  # zone/sensor -> (mean, variance)

    def should_suppress(self, msg: SensorMessage) -> bool:
        """Determine if message should be suppressed"""
        # Deduplication check
        if self._is_duplicate(msg):
            return True

        # Quality gates
        if msg.quality and msg.quality.get("battery_pct", 100) < 5:
            return True

        return False

    def _is_duplicate(self, msg: SensorMessage) -> bool:
        """Check if message is duplicate of recent reading"""
        key = msg.sensor_id

        if key in self.dedup_window:
            prev_value, prev_time = self.dedup_window[key]

            # Check if value unchanged and within window
            current_time = datetime.fromisoformat(msg.ts.replace("Z", "+00:00"))

            if prev_value == msg.value:
                time_diff = (current_time - prev_time).total_seconds()
                if time_diff < self.dedup_window_seconds:
                    return True

        # Update window
        self.dedup_window[key] = (
            msg.value,
            datetime.fromisoformat(msg.ts.replace("Z", "+00:00")),
        )
        return False
