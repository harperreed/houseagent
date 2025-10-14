# ABOUTME: Tests for statistical anomaly detection using Z-score method
# ABOUTME: Validates per-sensor/zone statistics and threshold configuration

from datetime import datetime
from houseagent.anomaly_detector import AnomalyDetector
from houseagent.schemas import SensorMessage


def test_anomaly_detector_flags_outliers():
    """Test AnomalyDetector flags readings beyond threshold"""
    detector = AnomalyDetector(z_threshold=2.0)

    # Build baseline with normal readings
    for temp in [20.0, 21.0, 20.5, 21.5, 20.8]:
        msg = SensorMessage(
            ts=datetime.now().isoformat(),
            sensor_id="temp_01",
            sensor_type="temperature",
            zone_id="lobby",
            value={"celsius": temp},
        )
        detector.is_anomalous(msg)

    # Send anomalous reading
    anomaly_msg = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 45.0},  # Way outside normal range
    )

    assert detector.is_anomalous(anomaly_msg)
    assert detector.score > 2.0


def test_anomaly_detector_allows_normal_readings():
    """Test AnomalyDetector doesn't flag normal variation"""
    detector = AnomalyDetector(z_threshold=2.0)

    # Send normal readings
    for temp in [20.0, 21.0, 20.5, 21.5, 20.8, 21.2]:
        msg = SensorMessage(
            ts=datetime.now().isoformat(),
            sensor_id="temp_01",
            sensor_type="temperature",
            zone_id="lobby",
            value={"celsius": temp},
        )
        is_anomalous = detector.is_anomalous(msg)

    # Last normal reading should not be flagged
    assert not is_anomalous
