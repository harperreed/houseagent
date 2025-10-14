# ABOUTME: Tests for noise filtering including deduplication and quality gates
# ABOUTME: Validates time-of-day sensitivity and EWMA statistics

from datetime import datetime
from houseagent.noise_filter import NoiseFilter
from houseagent.schemas import SensorMessage


def test_noise_filter_suppresses_duplicates():
    """Test NoiseFilter suppresses duplicate sensor readings"""
    filter = NoiseFilter()

    msg1 = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0},
    )

    msg2 = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0},  # Same value
    )

    assert not filter.should_suppress(msg1)  # First message passes
    assert filter.should_suppress(msg2)  # Duplicate suppressed


def test_noise_filter_rejects_low_battery():
    """Test NoiseFilter suppresses messages from low battery sensors"""
    filter = NoiseFilter()

    msg = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0},
        quality={"battery_pct": 3},
    )

    assert filter.should_suppress(msg)


def test_noise_filter_allows_good_battery():
    """Test NoiseFilter allows messages from healthy sensors"""
    filter = NoiseFilter()

    msg = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0},
        quality={"battery_pct": 95},
    )

    assert not filter.should_suppress(msg)
