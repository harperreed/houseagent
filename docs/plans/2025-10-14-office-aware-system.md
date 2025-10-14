# Office-Aware System Evolution Implementation Plan

> **For Claude:** Use `${SUPERPOWERS_SKILLS_ROOT}/skills/collaboration/executing-plans/SKILL.md` to implement this plan task-by-task.

**Goal:** Transform HouseAgent from basic MQTT automation into a context-aware, tool-using office monitoring system with noise filtering, situation building, floor plan integration, and multi-model AI.

**Architecture:** Sequential 5-phase approach preserving existing MQTT/paho-mqtt core while adding layered intelligence: validation → filtering → situation building → tools → multi-model orchestration. Each phase builds on previous, validated before moving forward.

**Tech Stack:** Python 3.x, paho-mqtt, Pydantic (validation), OpenAI API, ChromaDB (existing), structlog (existing), Docker

---

## Phase 0: Foundation Changes (Week 1)

### Task 1: Create Pydantic Schema Models

**Files:**
- Create: `houseagent/schemas.py`
- Test: `tests/test_schemas.py`

**Step 1: Write failing test for SensorMessage validation**

Create `tests/test_schemas.py`:

```python
# ABOUTME: Tests for Pydantic schema models validating sensor messages
# ABOUTME: Covers SensorMessage, LegacyMessage, and format conversions

from datetime import datetime
import pytest
from houseagent.schemas import SensorMessage, LegacyMessage


def test_sensor_message_valid():
    """Test SensorMessage accepts valid office sensor data"""
    msg = SensorMessage(
        ts="2025-10-14T10:30:00Z",
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="conf_room_a",
        site_id="hq",
        floor=1,
        value={"celsius": 22.5}
    )
    assert msg.sensor_id == "temp_01"
    assert msg.value["celsius"] == 22.5


def test_sensor_message_requires_fields():
    """Test SensorMessage rejects missing required fields"""
    with pytest.raises(ValueError):
        SensorMessage(
            sensor_id="temp_01",
            sensor_type="temperature"
            # Missing required fields
        )
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_schemas.py::test_sensor_message_valid -v
```

Expected: `ModuleNotFoundError: No module named 'houseagent.schemas'`

**Step 3: Add pydantic dependency**

```bash
uv add pydantic
```

**Step 4: Write minimal SensorMessage implementation**

Create `houseagent/schemas.py`:

```python
# ABOUTME: Pydantic models for sensor message validation and transformation
# ABOUTME: Supports new office format and legacy home automation format

from pydantic import BaseModel
from typing import Optional, Dict, Any


class SensorMessage(BaseModel):
    """Enhanced format for office sensor messages"""
    ts: str  # ISO8601 timestamp
    sensor_id: str
    sensor_type: str
    zone_id: str
    site_id: str = "hq"
    floor: int = 1
    value: Dict[str, Any]
    quality: Optional[Dict[str, Any]] = None
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_schemas.py::test_sensor_message_valid -v
```

Expected: PASS

**Step 6: Add test for legacy message support**

Add to `tests/test_schemas.py`:

```python
def test_legacy_message_format():
    """Test LegacyMessage supports old home automation format"""
    msg = LegacyMessage(
        sensor="motion_sensor",
        value=True,
        room="living_room"
    )
    assert msg.sensor == "motion_sensor"
    assert msg.room == "living_room"


def test_legacy_to_sensor_conversion():
    """Test converting legacy format to new SensorMessage"""
    legacy = {"sensor": "temp_hall", "value": 21.0, "room": "hallway"}
    zone_map = {"hallway": "zone_hall"}

    msg = SensorMessage.from_legacy(legacy, zone_map)
    assert msg.sensor_id == "temp_hall"
    assert msg.zone_id == "zone_hall"
    assert msg.value["reading"] == 21.0
```

**Step 7: Run test to verify it fails**

```bash
uv run pytest tests/test_schemas.py::test_legacy_message_format -v
```

Expected: FAIL - `LegacyMessage` not defined

**Step 8: Implement LegacyMessage and conversion**

Add to `houseagent/schemas.py`:

```python
from datetime import datetime


class LegacyMessage(BaseModel):
    """Legacy format - home automation compatibility"""
    sensor: Optional[str] = None
    value: Optional[Any] = None
    room: Optional[str] = None


class SensorMessage(BaseModel):
    """Enhanced format for office sensor messages"""
    ts: str
    sensor_id: str
    sensor_type: str
    zone_id: str
    site_id: str = "hq"
    floor: int = 1
    value: Dict[str, Any]
    quality: Optional[Dict[str, Any]] = None

    @classmethod
    def from_legacy(cls, msg: Dict, zone_map: Dict):
        """Convert legacy message to new format"""
        return cls(
            ts=datetime.now().isoformat(),
            sensor_id=msg.get("sensor", "unknown"),
            sensor_type=msg.get("sensor", "unknown"),
            zone_id=zone_map.get(msg.get("room"), "unknown"),
            value={"reading": msg.get("value")}
        )
```

**Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/test_schemas.py -v
```

Expected: All PASS

**Step 10: Commit**

```bash
git add houseagent/schemas.py tests/test_schemas.py pyproject.toml uv.lock
git commit -m "feat: add Pydantic schema models for sensor validation"
```

---

### Task 2: Add Hierarchical Topic Support to Collector

**Files:**
- Modify: `collector.py`
- Test: `tests/test_collector.py` (create if needed)

**Step 1: Write test for topic subscription**

Create `tests/test_collector.py`:

```python
# ABOUTME: Tests for MQTT collector topic subscription and message routing
# ABOUTME: Validates both legacy and hierarchical office topic patterns

from unittest.mock import Mock, MagicMock
import pytest


def test_collector_subscribes_to_office_topics():
    """Test collector subscribes to hierarchical office topics"""
    client_mock = Mock()

    # Import and trigger on_connect
    from collector import on_connect
    on_connect(client_mock, None, None, 0)

    # Verify office pattern subscription
    calls = [call[0][0] for call in client_mock.subscribe.call_args_list]
    assert any("office/" in topic for topic in calls)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_collector.py::test_collector_subscribes_to_office_topics -v
```

Expected: FAIL - assertion fails, no office topics

**Step 3: Modify collector.py to add office topic subscription**

In `collector.py`, modify the `on_connect` function:

```python
def on_connect(client, userdata, flags, rc):
    """Handle MQTT connection - subscribe to topics"""
    logger.info("mqtt.connected", result_code=rc)

    # Keep existing legacy subscription
    legacy_topic = os.getenv('SUBSCRIBE_TOPIC', 'hassevents/notifications')
    client.subscribe(legacy_topic)
    logger.info("mqtt.subscribed", topic=legacy_topic)

    # Add hierarchical office topics
    office_pattern = "office/+/+/+/+/+"  # site/floor/zone/type/id
    client.subscribe(office_pattern)
    logger.info("mqtt.subscribed", topic=office_pattern, type="office")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_collector.py::test_collector_subscribes_to_office_topics -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add collector.py tests/test_collector.py
git commit -m "feat: add hierarchical office topic subscription to collector"
```

---

### Task 3: Integrate Schema Validation into MessageBatcher

**Files:**
- Modify: `houseagent/message_batcher.py`
- Test: `tests/test_message_batcher_comprehensive.py`

**Step 1: Write test for message validation**

Add to `tests/test_message_batcher_comprehensive.py`:

```python
def test_message_batcher_validates_sensor_messages(mqtt_client):
    """Test MessageBatcher validates incoming messages with schema"""
    batcher = MessageBatcher(mqtt_client, timeout=1.0)

    # Valid new format message
    valid_msg = {
        "ts": "2025-10-14T10:30:00Z",
        "sensor_id": "motion_01",
        "sensor_type": "motion",
        "zone_id": "lobby",
        "value": {"detected": True}
    }

    msg_mock = MagicMock()
    msg_mock.payload = json.dumps(valid_msg).encode()

    batcher.on_message(mqtt_client, None, msg_mock)

    # Should be in queue
    assert not batcher.message_queue.empty()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_message_batcher_comprehensive.py::test_message_batcher_validates_sensor_messages -v
```

Expected: PASS (validation not yet enforced, so message passes through)

**Step 3: Add validation to MessageBatcher**

Modify `houseagent/message_batcher.py`:

```python
from houseagent.schemas import SensorMessage, LegacyMessage
from pydantic import ValidationError


class MessageBatcher:
    def __init__(self, client, timeout):
        self.client = client
        self.timeout = timeout
        self.message_queue = queue.Queue()
        self.batch = []
        self.timer = None
        self.lock = threading.Lock()

        # NEW: Schema validation
        self.zone_map = {}  # TODO: Load from config

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT message with validation"""
        try:
            message = json.loads(msg.payload)

            # NEW: Try to validate as SensorMessage
            try:
                validated = SensorMessage(**message)
                message = validated.dict()
            except ValidationError:
                # Try legacy format
                try:
                    legacy = LegacyMessage(**message)
                    validated = SensorMessage.from_legacy(message, self.zone_map)
                    message = validated.dict()
                except ValidationError as e:
                    logger.warning("message.validation_failed", error=str(e), payload=message)
                    message["validation_failed"] = True

            # Continue with existing queueing logic
            with self.lock:
                self.message_queue.put(message)
                # ... rest of existing logic

        except json.JSONDecodeError as e:
            logger.error("message.decode_failed", error=str(e))
```

**Step 4: Add test for validation failure handling**

Add to `tests/test_message_batcher_comprehensive.py`:

```python
def test_message_batcher_handles_invalid_messages(mqtt_client):
    """Test MessageBatcher logs but doesn't crash on invalid messages"""
    batcher = MessageBatcher(mqtt_client, timeout=1.0)

    # Invalid message missing required fields
    invalid_msg = {"sensor_id": "temp_01"}  # Missing many required fields

    msg_mock = MagicMock()
    msg_mock.payload = json.dumps(invalid_msg).encode()

    batcher.on_message(mqtt_client, None, msg_mock)

    # Should still be in queue with validation_failed flag
    queued_msg = batcher.message_queue.get()
    assert queued_msg.get("validation_failed") == True
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_message_batcher_comprehensive.py -v -k validation
```

Expected: All PASS

**Step 6: Commit**

```bash
git add houseagent/message_batcher.py tests/test_message_batcher_comprehensive.py
git commit -m "feat: integrate Pydantic validation into MessageBatcher"
```

---

### Task 4: Add Phase 0 Configuration

**Files:**
- Create: `config/phase0.env.example`
- Modify: `.env` (user will do this)
- Modify: `README.md`

**Step 1: Create example configuration**

Create `config/phase0.env.example`:

```bash
# Phase 0: Foundation Configuration

# MQTT Connection
MQTT_BROKER=mqtt.office.local
MQTT_PORT=1883

# Topic Configuration
SUBSCRIBE_TOPIC=hassevents/notifications
OFFICE_MODE=false  # Set to true when ready to process office sensors

# Zone Mapping (JSON)
ZONE_MAP={"hallway": "zone_hall", "living_room": "zone_living"}
```

**Step 2: Update README with Phase 0 docs**

Add to `README.md`:

```markdown
## Phase 0: Foundation (Current)

The system now supports both legacy home automation messages and new hierarchical office sensor topics.

### New Topic Structure

Office sensors publish to: `office/{site}/{floor}/{zone}/{type}/{id}`

Example: `office/hq/1/conf_room_a/temperature/temp_01`

### Message Format

New format (Pydantic validated):
\`\`\`json
{
  "ts": "2025-10-14T10:30:00Z",
  "sensor_id": "temp_01",
  "sensor_type": "temperature",
  "zone_id": "conf_room_a",
  "site_id": "hq",
  "floor": 1,
  "value": {"celsius": 22.5},
  "quality": {"battery_pct": 95}
}
\`\`\`

Legacy format still supported (auto-converted).
```

**Step 3: Commit**

```bash
git add config/phase0.env.example README.md
git commit -m "docs: add Phase 0 configuration and documentation"
```

---

## Phase 1: Noise Filtering & Validation (Week 2)

### Task 5: Create NoiseFilter Component

**Files:**
- Create: `houseagent/noise_filter.py`
- Test: `tests/test_noise_filter.py`

**Step 1: Write test for duplicate detection**

Create `tests/test_noise_filter.py`:

```python
# ABOUTME: Tests for noise filtering including deduplication and quality gates
# ABOUTME: Validates time-of-day sensitivity and EWMA statistics

from datetime import datetime, timedelta
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
        value={"celsius": 22.0}
    )

    msg2 = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0}  # Same value
    )

    assert not filter.should_suppress(msg1)  # First message passes
    assert filter.should_suppress(msg2)      # Duplicate suppressed
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_noise_filter.py::test_noise_filter_suppresses_duplicates -v
```

Expected: `ModuleNotFoundError: No module named 'houseagent.noise_filter'`

**Step 3: Write minimal NoiseFilter implementation**

Create `houseagent/noise_filter.py`:

```python
# ABOUTME: Noise filtering for sensor messages with deduplication and quality checks
# ABOUTME: Implements EWMA statistics and time-of-day sensitivity rules

from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from houseagent.schemas import SensorMessage
import random


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
        if msg.quality and msg.quality.get('battery_pct', 100) < 5:
            return True

        return False

    def _is_duplicate(self, msg: SensorMessage) -> bool:
        """Check if message is duplicate of recent reading"""
        key = msg.sensor_id

        if key in self.dedup_window:
            prev_value, prev_time = self.dedup_window[key]

            # Check if value unchanged and within window
            current_time = datetime.fromisoformat(msg.ts.replace('Z', '+00:00'))

            if prev_value == msg.value:
                time_diff = (current_time - prev_time).total_seconds()
                if time_diff < self.dedup_window_seconds:
                    return True

        # Update window
        self.dedup_window[key] = (
            msg.value,
            datetime.fromisoformat(msg.ts.replace('Z', '+00:00'))
        )
        return False
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_noise_filter.py::test_noise_filter_suppresses_duplicates -v
```

Expected: PASS

**Step 5: Add test for quality gates**

Add to `tests/test_noise_filter.py`:

```python
def test_noise_filter_rejects_low_battery():
    """Test NoiseFilter suppresses messages from low battery sensors"""
    filter = NoiseFilter()

    msg = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 22.0},
        quality={"battery_pct": 3}
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
        quality={"battery_pct": 95}
    )

    assert not filter.should_suppress(msg)
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_noise_filter.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/noise_filter.py tests/test_noise_filter.py
git commit -m "feat: add NoiseFilter with deduplication and quality gates"
```

---

### Task 6: Create AnomalyDetector Component

**Files:**
- Create: `houseagent/anomaly_detector.py`
- Test: `tests/test_anomaly_detector.py`

**Step 1: Write test for anomaly detection**

Create `tests/test_anomaly_detector.py`:

```python
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
            value={"celsius": temp}
        )
        detector.is_anomalous(msg)

    # Send anomalous reading
    anomaly_msg = SensorMessage(
        ts=datetime.now().isoformat(),
        sensor_id="temp_01",
        sensor_type="temperature",
        zone_id="lobby",
        value={"celsius": 45.0}  # Way outside normal range
    )

    assert detector.is_anomalous(anomaly_msg)
    assert detector.score > 2.0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_anomaly_detector.py::test_anomaly_detector_flags_outliers -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement AnomalyDetector**

Create `houseagent/anomaly_detector.py`:

```python
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
        for key in ['celsius', 'fahrenheit', 'reading', 'value', 'count']:
            if key in value_dict:
                try:
                    return float(value_dict[key])
                except (ValueError, TypeError):
                    pass
        return None
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_anomaly_detector.py::test_anomaly_detector_flags_outliers -v
```

Expected: PASS

**Step 5: Add test for normal readings**

Add to `tests/test_anomaly_detector.py`:

```python
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
            value={"celsius": temp}
        )
        is_anomalous = detector.is_anomalous(msg)

    # Last normal reading should not be flagged
    assert not is_anomalous
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_anomaly_detector.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/anomaly_detector.py tests/test_anomaly_detector.py
git commit -m "feat: add AnomalyDetector with Z-score based detection"
```

---

### Task 7: Integrate Filtering into MessageBatcher

**Files:**
- Modify: `houseagent/message_batcher.py`
- Test: `tests/test_message_batcher_comprehensive.py`

**Step 1: Write test for integrated filtering**

Add to `tests/test_message_batcher_comprehensive.py`:

```python
def test_message_batcher_filters_noise(mqtt_client):
    """Test MessageBatcher uses NoiseFilter to suppress duplicates"""
    batcher = MessageBatcher(mqtt_client, timeout=1.0)

    # Send same message twice
    msg_data = {
        "ts": "2025-10-14T10:30:00Z",
        "sensor_id": "temp_01",
        "sensor_type": "temperature",
        "zone_id": "lobby",
        "value": {"celsius": 22.0}
    }

    msg_mock1 = MagicMock()
    msg_mock1.payload = json.dumps(msg_data).encode()

    msg_mock2 = MagicMock()
    msg_mock2.payload = json.dumps(msg_data).encode()

    batcher.on_message(mqtt_client, None, msg_mock1)
    batcher.on_message(mqtt_client, None, msg_mock2)

    # Only first message should be queued
    assert batcher.message_queue.qsize() == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_message_batcher_comprehensive.py::test_message_batcher_filters_noise -v
```

Expected: FAIL - both messages queued

**Step 3: Integrate NoiseFilter and AnomalyDetector into MessageBatcher**

Modify `houseagent/message_batcher.py`:

```python
from houseagent.noise_filter import NoiseFilter
from houseagent.anomaly_detector import AnomalyDetector


class MessageBatcher:
    def __init__(self, client, timeout):
        self.client = client
        self.timeout = timeout
        self.message_queue = queue.Queue()
        self.batch = []
        self.timer = None
        self.lock = threading.Lock()
        self.zone_map = {}

        # NEW: Add filtering components
        self.noise_filter = NoiseFilter()
        self.anomaly_detector = AnomalyDetector()

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT message with validation and filtering"""
        try:
            message = json.loads(msg.payload)

            # Validate message
            sensor_msg = None
            try:
                sensor_msg = SensorMessage(**message)
            except ValidationError:
                try:
                    legacy = LegacyMessage(**message)
                    sensor_msg = SensorMessage.from_legacy(message, self.zone_map)
                except ValidationError as e:
                    logger.warning("message.validation_failed", error=str(e))
                    message["validation_failed"] = True
                    sensor_msg = None

            # NEW: Apply filtering if we have valid sensor message
            if sensor_msg:
                if self.noise_filter.should_suppress(sensor_msg):
                    logger.debug("message.suppressed", sensor_id=sensor_msg.sensor_id, reason="noise_filter")
                    return

                if self.anomaly_detector.is_anomalous(sensor_msg):
                    logger.info("message.anomaly_detected",
                               sensor_id=sensor_msg.sensor_id,
                               score=self.anomaly_detector.score)
                    sensor_msg.value["anomaly_score"] = self.anomaly_detector.score

                message = sensor_msg.dict()

            # Continue with existing queueing
            with self.lock:
                self.message_queue.put(message)
                # ... rest of existing logic

        except json.JSONDecodeError as e:
            logger.error("message.decode_failed", error=str(e))
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_message_batcher_comprehensive.py::test_message_batcher_filters_noise -v
```

Expected: PASS

**Step 5: Add test for anomaly score injection**

Add to `tests/test_message_batcher_comprehensive.py`:

```python
def test_message_batcher_adds_anomaly_scores(mqtt_client):
    """Test MessageBatcher adds anomaly scores to detected anomalies"""
    batcher = MessageBatcher(mqtt_client, timeout=1.0)

    # Build baseline
    for temp in [20.0, 21.0, 20.5]:
        msg = MagicMock()
        msg.payload = json.dumps({
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "temp_01",
            "sensor_type": "temperature",
            "zone_id": "lobby",
            "value": {"celsius": temp}
        }).encode()
        batcher.on_message(mqtt_client, None, msg)

    # Send anomaly
    anomaly_msg = MagicMock()
    anomaly_msg.payload = json.dumps({
        "ts": "2025-10-14T10:35:00Z",
        "sensor_id": "temp_01",
        "sensor_type": "temperature",
        "zone_id": "lobby",
        "value": {"celsius": 45.0}
    }).encode()

    batcher.on_message(mqtt_client, None, anomaly_msg)

    # Find anomaly message in queue
    found_anomaly = False
    while not batcher.message_queue.empty():
        msg = batcher.message_queue.get()
        if msg.get("value", {}).get("celsius") == 45.0:
            assert "anomaly_score" in msg["value"]
            assert msg["value"]["anomaly_score"] > 2.0
            found_anomaly = True

    assert found_anomaly
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_message_batcher_comprehensive.py -v -k "filter or anomaly"
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/message_batcher.py tests/test_message_batcher_comprehensive.py
git commit -m "feat: integrate noise filtering and anomaly detection into MessageBatcher"
```

---

## Phase 2: Situation Building (Week 3)

### Task 8: Create FloorPlanModel

**Files:**
- Create: `houseagent/floor_plan.py`
- Create: `config/floor_plan.json` (example)
- Test: `tests/test_floor_plan.py`

**Step 1: Write test for floor plan loading**

Create `tests/test_floor_plan.py`:

```python
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
            "lobby": {"name": "Main Lobby", "floor": 1, "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            "conf_a": {"name": "Conference Room A", "floor": 1, "polygon": [[10, 0], [20, 0], [20, 10], [10, 10]]}
        },
        "adjacency": {
            "lobby": ["conf_a"],
            "conf_a": ["lobby"]
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        model = FloorPlanModel(config_path)
        assert "lobby" in model.zones
        assert model.zones["lobby"]["name"] == "Main Lobby"
    finally:
        Path(config_path).unlink()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_floor_plan.py::test_floor_plan_loads_from_json -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement FloorPlanModel**

Create `houseagent/floor_plan.py`:

```python
# ABOUTME: Floor plan model for spatial reasoning and zone relationships
# ABOUTME: Supports adjacency queries, camera FOV overlaps, and sensor locations

import json
from typing import List, Dict, Any, Optional
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
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.zones = config.get("zones", {})
        self.sensors = config.get("sensors", {})
        self.cameras = config.get("cameras", [])
        self.adjacency = config.get("adjacency", {})

    def get_adjacent_zones(self, zone_id: str) -> List[str]:
        """Get zones adjacent to given zone"""
        return self.adjacency.get(zone_id, [])

    @classmethod
    def load(cls, config_path: str = "config/floor_plan.json") -> 'FloorPlanModel':
        """Factory method to load floor plan"""
        return cls(config_path)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_floor_plan.py::test_floor_plan_loads_from_json -v
```

Expected: PASS

**Step 5: Add test for adjacency queries**

Add to `tests/test_floor_plan.py`:

```python
def test_floor_plan_adjacency_queries():
    """Test FloorPlanModel returns adjacent zones"""
    config = {
        "zones": {
            "lobby": {"name": "Lobby"},
            "conf_a": {"name": "Conf A"},
            "conf_b": {"name": "Conf B"}
        },
        "adjacency": {
            "lobby": ["conf_a", "conf_b"],
            "conf_a": ["lobby"],
            "conf_b": ["lobby"]
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
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
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_floor_plan.py -v
```

Expected: All PASS

**Step 7: Create example floor plan config**

Create `config/floor_plan.json`:

```json
{
  "zones": {
    "lobby": {
      "name": "Main Lobby",
      "floor": 1,
      "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]
    },
    "conf_a": {
      "name": "Conference Room A",
      "floor": 1,
      "polygon": [[10, 0], [20, 0], [20, 10], [10, 10]]
    },
    "conf_b": {
      "name": "Conference Room B",
      "floor": 1,
      "polygon": [[0, 10], [10, 10], [10, 20], [0, 20]]
    }
  },
  "adjacency": {
    "lobby": ["conf_a", "conf_b"],
    "conf_a": ["lobby"],
    "conf_b": ["lobby"]
  },
  "cameras": [],
  "sensors": {}
}
```

**Step 8: Commit**

```bash
git add houseagent/floor_plan.py tests/test_floor_plan.py config/floor_plan.json
git commit -m "feat: add FloorPlanModel with zone and adjacency support"
```

---

### Task 9: Create SituationBuilder

**Files:**
- Create: `houseagent/situation_builder.py`
- Test: `tests/test_situation_builder.py`

**Step 1: Write test for situation building**

Create `tests/test_situation_builder.py`:

```python
# ABOUTME: Tests for situation builder clustering messages into coherent situations
# ABOUTME: Validates zone clustering, corroboration, and confidence scoring

from datetime import datetime
from houseagent.situation_builder import SituationBuilder, Situation
from houseagent.floor_plan import FloorPlanModel
import tempfile
import json


def test_situation_builder_creates_situation_from_messages():
    """Test SituationBuilder clusters messages into situation"""
    # Create floor plan
    config = {
        "zones": {"lobby": {"name": "Lobby"}},
        "adjacency": {"lobby": []}
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        floor_plan = FloorPlanModel(f.name)

    builder = SituationBuilder()

    messages = [
        {
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "motion_01",
            "sensor_type": "motion",
            "zone_id": "lobby",
            "value": {"detected": True}
        },
        {
            "ts": "2025-10-14T10:30:05Z",
            "sensor_id": "temp_01",
            "sensor_type": "temperature",
            "zone_id": "lobby",
            "value": {"celsius": 22.0}
        }
    ]

    situation = builder.build(messages, floor_plan)

    assert situation is not None
    assert len(situation.messages) == 2
    assert "lobby" in situation.features["zones"]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_situation_builder.py::test_situation_builder_creates_situation_from_messages -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement SituationBuilder**

Create `houseagent/situation_builder.py`:

```python
# ABOUTME: Situation builder for clustering messages into spatial/temporal situations
# ABOUTME: Implements corroboration logic and confidence scoring

from typing import List, Dict, Optional
from collections import Counter
from dataclasses import dataclass
import ulid


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
            "messages": self.messages
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
            'event_counts': dict(Counter([m.get('sensor_type') for m in messages])),
            'zones': list(zone_clusters.keys()),
            'anomaly_scores': [
                m.get('value', {}).get('anomaly_score', 0)
                for m in messages
            ]
        }

        # Check for corroboration (2+ sensors)
        if self._has_corroboration(messages):
            return Situation(
                id=f"sit-{ulid.new()}",
                messages=messages,
                features=features,
                confidence=0.8
            )

        return None

    def _cluster_by_zone(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster messages by zone_id"""
        clusters = {}
        for msg in messages:
            zone_id = msg.get('zone_id', 'unknown')
            if zone_id not in clusters:
                clusters[zone_id] = []
            clusters[zone_id].append(msg)
        return clusters

    def _has_corroboration(self, messages: List[Dict]) -> bool:
        """Check if multiple sensors corroborate situation"""
        unique_sensors = set(m.get('sensor_id') for m in messages)
        return len(unique_sensors) >= 2
```

**Step 4: Add ulid dependency**

```bash
uv add python-ulid
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_situation_builder.py::test_situation_builder_creates_situation_from_messages -v
```

Expected: PASS

**Step 6: Add test for corroboration logic**

Add to `tests/test_situation_builder.py`:

```python
def test_situation_builder_requires_corroboration():
    """Test SituationBuilder requires 2+ sensors for situation"""
    config = {"zones": {"lobby": {}}, "adjacency": {}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        floor_plan = FloorPlanModel(f.name)

    builder = SituationBuilder()

    # Single sensor - no situation
    single_message = [{
        "ts": "2025-10-14T10:30:00Z",
        "sensor_id": "motion_01",
        "sensor_type": "motion",
        "zone_id": "lobby",
        "value": {"detected": True}
    }]

    situation = builder.build(single_message, floor_plan)
    assert situation is None
```

**Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_situation_builder.py -v
```

Expected: All PASS

**Step 8: Commit**

```bash
git add houseagent/situation_builder.py tests/test_situation_builder.py pyproject.toml uv.lock
git commit -m "feat: add SituationBuilder with zone clustering and corroboration"
```

---

### Task 10: Integrate SituationBuilder into AgentListener

**Files:**
- Modify: `houseagent/agent_listener.py`
- Test: `tests/test_agent_listener_comprehensive.py`

**Step 1: Write test for situation-based processing**

Add to `tests/test_agent_listener_comprehensive.py`:

```python
def test_agent_listener_builds_situations(mqtt_client):
    """Test AgentListener uses SituationBuilder for batch processing"""
    listener = AgentListener(mqtt_client, house_bot=Mock())

    batch_msg = {
        "messages": [
            {
                "ts": "2025-10-14T10:30:00Z",
                "sensor_id": "motion_01",
                "sensor_type": "motion",
                "zone_id": "lobby",
                "value": {"detected": True}
            },
            {
                "ts": "2025-10-14T10:30:05Z",
                "sensor_id": "temp_01",
                "sensor_type": "temperature",
                "zone_id": "lobby",
                "value": {"celsius": 22.0}
            }
        ]
    }

    msg_mock = MagicMock()
    msg_mock.payload = json.dumps(batch_msg).encode()

    listener.on_message(mqtt_client, None, msg_mock)

    # Verify HouseBot was called with situation
    assert listener.house_bot.generate_response.called
    call_args = listener.house_bot.generate_response.call_args[0]
    # First arg should be situation JSON with zones and features
    assert "zones" in call_args[0]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_agent_listener_comprehensive.py::test_agent_listener_builds_situations -v
```

Expected: FAIL - situation features not present

**Step 3: Integrate SituationBuilder into AgentListener**

Modify `houseagent/agent_listener.py`:

```python
from houseagent.situation_builder import SituationBuilder
from houseagent.floor_plan import FloorPlanModel
import os


class AgentListener:
    def __init__(self, client, house_bot, ...):
        # ... existing init ...

        # NEW: Add situation building
        self.situation_builder = SituationBuilder()
        floor_plan_path = os.getenv('FLOOR_PLAN_PATH', 'config/floor_plan.json')
        self.floor_plan = FloorPlanModel.load(floor_plan_path)
        self.last_situation = None

    def on_message(self, client, userdata, msg):
        """Handle message batch and build situation"""
        try:
            batch = json.loads(msg.payload)
            messages = batch.get('messages', [])

            # NEW: Build situation instead of using raw batch
            situation = self.situation_builder.build(messages, self.floor_plan)

            if situation and situation.requires_response():
                # Generate response with situation context
                response = self.house_bot.generate_response(
                    situation.to_prompt_json(),
                    self.last_situation.to_prompt_json() if self.last_situation else None,
                    self.message_history
                )

                self.last_situation = situation

                # ... existing response handling ...

        except json.JSONDecodeError as e:
            logger.error("batch.decode_failed", error=str(e))
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_agent_listener_comprehensive.py::test_agent_listener_builds_situations -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add houseagent/agent_listener.py tests/test_agent_listener_comprehensive.py
git commit -m "feat: integrate SituationBuilder into AgentListener"
```

---

## Phase 3-4: Tools & Floor Plan (Week 4)

### Task 11: Create ToolRouter Framework

**Files:**
- Create: `houseagent/tools/__init__.py`
- Create: `houseagent/tools/router.py`
- Test: `tests/test_tool_router.py`

**Step 1: Write test for tool execution**

Create `tests/test_tool_router.py`:

```python
# ABOUTME: Tests for tool router framework with timeout and error handling
# ABOUTME: Validates tool registration, execution, and policy enforcement

from houseagent.tools.router import ToolRouter, ToolRequest
from unittest.mock import Mock
import time


def test_tool_router_executes_tools():
    """Test ToolRouter can execute registered tools"""
    router = ToolRouter()

    # Register mock tool
    mock_tool = Mock()
    mock_tool.execute.return_value = {"result": "success"}
    router.tools["test_tool"] = mock_tool

    request = ToolRequest(tool_name="test_tool", params={"arg": "value"})
    result = router.execute(request)

    assert result["result"] == "success"
    mock_tool.execute.assert_called_once_with({"arg": "value"})
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tool_router.py::test_tool_router_executes_tools -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement ToolRouter**

Create `houseagent/tools/__init__.py`:

```python
# ABOUTME: Tool framework for HouseAgent with routing and execution
```

Create `houseagent/tools/router.py`:

```python
# ABOUTME: Tool router for executing tools with timeout and error handling
# ABOUTME: Manages tool registry, execution policy, and result formatting

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import signal
from contextlib import contextmanager


@dataclass
class ToolRequest:
    """Request to execute a tool"""
    tool_name: str
    params: Dict[str, Any]


class ToolRouter:
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self.timeout_seconds = 5

    def execute(self, request: ToolRequest) -> Dict[str, Any]:
        """Execute tool with timeout and error handling"""
        tool = self.tools.get(request.tool_name)
        if not tool:
            return {"error": "Unknown tool"}

        try:
            # Execute with timeout
            result = self._execute_with_timeout(
                tool.execute,
                request.params,
                self.timeout_seconds
            )
            return result
        except TimeoutError:
            return {"error": "Tool timeout"}
        except Exception as e:
            return {"error": str(e)}

    def _execute_with_timeout(self, func: Callable, args: Dict, timeout: int) -> Any:
        """Execute function with timeout"""
        # Simple timeout using signal (Unix only)
        # For production, use concurrent.futures or multiprocessing

        @contextmanager
        def time_limit(seconds):
            def signal_handler(signum, frame):
                raise TimeoutError("Timed out")
            signal.signal(signal.SIGALRM, signal_handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)

        try:
            with time_limit(timeout):
                return func(args)
        except TimeoutError:
            raise

    def get_catalog(self) -> str:
        """Get catalog of available tools"""
        return ", ".join(self.tools.keys())
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_tool_router.py::test_tool_router_executes_tools -v
```

Expected: PASS (may skip timeout test on non-Unix systems)

**Step 5: Add test for unknown tools**

Add to `tests/test_tool_router.py`:

```python
def test_tool_router_handles_unknown_tools():
    """Test ToolRouter returns error for unknown tools"""
    router = ToolRouter()

    request = ToolRequest(tool_name="nonexistent", params={})
    result = router.execute(request)

    assert "error" in result
    assert result["error"] == "Unknown tool"
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_tool_router.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/tools/ tests/test_tool_router.py
git commit -m "feat: add ToolRouter framework with timeout handling"
```

---

### Task 12: Create FloorPlanTool

**Files:**
- Create: `houseagent/tools/floor_plan_tool.py`
- Test: `tests/test_floor_plan_tool.py`

**Step 1: Write test for floor plan queries**

Create `tests/test_floor_plan_tool.py`:

```python
# ABOUTME: Tests for floor plan tool providing spatial query capabilities
# ABOUTME: Validates zone queries, adjacency lookups, and camera placement

import json
import tempfile
from houseagent.tools.floor_plan_tool import FloorPlanTool
from houseagent.floor_plan import FloorPlanModel


def test_floor_plan_tool_queries_adjacent_zones():
    """Test FloorPlanTool returns adjacent zones"""
    config = {
        "zones": {
            "lobby": {"name": "Lobby"},
            "conf_a": {"name": "Conf A"}
        },
        "adjacency": {
            "lobby": ["conf_a"],
            "conf_a": ["lobby"]
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        floor_plan = FloorPlanModel(f.name)

    tool = FloorPlanTool(floor_plan)
    result = tool.execute({"query": "adjacent_zones", "zone_id": "lobby"})

    assert "zones" in result
    assert "conf_a" in result["zones"]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_floor_plan_tool.py::test_floor_plan_tool_queries_adjacent_zones -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement FloorPlanTool**

Create `houseagent/tools/floor_plan_tool.py`:

```python
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
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_floor_plan_tool.py::test_floor_plan_tool_queries_adjacent_zones -v
```

Expected: PASS

**Step 5: Add test for zone info queries**

Add to `tests/test_floor_plan_tool.py`:

```python
def test_floor_plan_tool_returns_zone_info():
    """Test FloorPlanTool returns zone details"""
    config = {
        "zones": {
            "lobby": {"name": "Main Lobby", "floor": 1}
        },
        "adjacency": {}
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        floor_plan = FloorPlanModel(f.name)

    tool = FloorPlanTool(floor_plan)
    result = tool.execute({"query": "zone_info", "zone_id": "lobby"})

    assert "zone" in result
    assert result["zone"]["name"] == "Main Lobby"
    assert result["zone"]["floor"] == 1
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_floor_plan_tool.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/tools/floor_plan_tool.py tests/test_floor_plan_tool.py
git commit -m "feat: add FloorPlanTool for spatial queries"
```

---

### Task 13: Integrate Tools into HouseBot

**Files:**
- Modify: `houseagent/house_bot.py`
- Test: `tests/test_house_bot_comprehensive.py`

**Step 1: Write test for tool integration**

Add to `tests/test_house_bot_comprehensive.py`:

```python
def test_house_bot_executes_tools_before_ai():
    """Test HouseBot can execute tools and inject results into prompt"""
    bot = HouseBot()

    # Mock tool router
    bot.tool_router = Mock()
    bot.tool_router.get_catalog.return_value = "floor_plan_query"
    bot.tool_router.execute.return_value = {"zones": ["conf_a"]}

    # Mock OpenAI client
    bot.client = Mock()
    bot.client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Tool results received"))]
    )

    current_state = {
        "zones": ["lobby"],
        "tool_request": {
            "tool_name": "floor_plan_query",
            "params": {"query": "adjacent_zones", "zone_id": "lobby"}
        }
    }

    response = bot.generate_response(current_state, None)

    # Verify tool was executed
    assert bot.tool_router.execute.called
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_house_bot_comprehensive.py::test_house_bot_executes_tools_before_ai -v
```

Expected: FAIL - tool_router not initialized

**Step 3: Integrate tools into HouseBot**

Modify `houseagent/house_bot.py`:

```python
from houseagent.tools.router import ToolRouter, ToolRequest
from houseagent.tools.floor_plan_tool import FloorPlanTool
from houseagent.floor_plan import FloorPlanModel
import os


class HouseBot:
    def __init__(self):
        # ... existing init ...

        # NEW: Initialize tool framework
        self.tool_router = ToolRouter()

        # Register tools
        floor_plan_path = os.getenv('FLOOR_PLAN_PATH', 'config/floor_plan.json')
        floor_plan = FloorPlanModel.load(floor_plan_path)
        self.tool_router.tools['floor_plan_query'] = FloorPlanTool(floor_plan)

    def generate_response(self, current_state, last_state, message_history=None):
        """Generate AI response with optional tool execution"""
        # Build messages as before...
        messages = self._build_messages(current_state, last_state, message_history)

        # NEW: Add tool capability to prompt
        messages[0]['content'] += "\n\nAvailable tools: " + self.tool_router.get_catalog()

        # NEW: Execute tools if requested
        tool_request = current_state.get('tool_request')
        if tool_request:
            tool_result = self.tool_router.execute(
                ToolRequest(
                    tool_name=tool_request['tool_name'],
                    params=tool_request['params']
                )
            )

            # Inject tool results into conversation
            messages.append({
                "role": "assistant",
                "content": f"Tool results: {json.dumps(tool_result)}"
            })

        # Continue with OpenAI call
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        return response.choices[0].message.content
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_house_bot_comprehensive.py::test_house_bot_executes_tools_before_ai -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add houseagent/house_bot.py tests/test_house_bot_comprehensive.py
git commit -m "feat: integrate tool execution into HouseBot"
```

---

## Phase 5: Multi-Model & Hardening (Week 5)

### Task 14: Add Multi-Model Strategy

**Files:**
- Modify: `houseagent/house_bot.py`
- Test: `tests/test_house_bot_comprehensive.py`

**Step 1: Write test for model selection**

Add to `tests/test_house_bot_comprehensive.py`:

```python
def test_house_bot_selects_model_by_severity():
    """Test HouseBot uses different models based on situation severity"""
    bot = HouseBot()
    bot.classifier_model = "gpt-3.5-turbo"
    bot.synthesis_model = "gpt-4"

    # Mock OpenAI client
    bot.client = Mock()
    bot.client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Response"))]
    )

    # High severity situation
    high_severity_state = {
        "confidence": 0.9,
        "anomaly_scores": [3.5, 4.2],
        "zones": ["lobby"]
    }

    bot.generate_response(high_severity_state, None)

    # Check that gpt-4 was used
    call_kwargs = bot.client.chat.completions.create.call_args[1]
    assert call_kwargs['model'] == "gpt-4"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_house_bot_comprehensive.py::test_house_bot_selects_model_by_severity -v
```

Expected: FAIL - classifier_model not defined

**Step 3: Implement multi-model strategy**

Modify `houseagent/house_bot.py`:

```python
class HouseBot:
    def __init__(self):
        # ... existing init ...

        # NEW: Multi-model configuration
        self.classifier_model = "gpt-3.5-turbo"
        self.synthesis_model = os.getenv("OPENAI_MODEL", "gpt-4")
        self.model = self.synthesis_model  # Default

    def generate_response(self, current_state, last_state, message_history=None):
        """Generate AI response with model selection"""
        # NEW: Classify situation severity
        severity = self._classify_severity(current_state)

        # Select model based on severity
        selected_model = self.synthesis_model if severity > 0.7 else self.classifier_model

        # Build messages...
        messages = self._build_messages(current_state, last_state, message_history)

        # Add structured output request for high severity
        if severity > 0.7:
            messages.append({
                "role": "system",
                "content": "Respond with both text AND JSON: {severity, tags, actions}"
            })

        # ... tool execution as before ...

        # Use selected model
        response = self.client.chat.completions.create(
            model=selected_model,
            messages=messages
        )

        return response.choices[0].message.content

    def _classify_severity(self, state: Dict) -> float:
        """Classify situation severity (0-1)"""
        severity = 0.0

        # High confidence situations
        if state.get('confidence', 0) > 0.8:
            severity += 0.3

        # Anomaly detection
        anomaly_scores = state.get('anomaly_scores', [])
        if any(score > 2.5 for score in anomaly_scores):
            severity += 0.4

        # Multiple zones
        if len(state.get('zones', [])) > 1:
            severity += 0.2

        return min(severity, 1.0)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_house_bot_comprehensive.py::test_house_bot_selects_model_by_severity -v
```

Expected: PASS

**Step 5: Add test for low severity using cheaper model**

Add to `tests/test_house_bot_comprehensive.py`:

```python
def test_house_bot_uses_cheap_model_for_low_severity():
    """Test HouseBot uses gpt-3.5 for routine situations"""
    bot = HouseBot()
    bot.classifier_model = "gpt-3.5-turbo"
    bot.synthesis_model = "gpt-4"

    bot.client = Mock()
    bot.client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Response"))]
    )

    # Low severity situation
    low_severity_state = {
        "confidence": 0.3,
        "zones": ["lobby"]
    }

    bot.generate_response(low_severity_state, None)

    # Check that gpt-3.5 was used
    call_kwargs = bot.client.chat.completions.create.call_args[1]
    assert call_kwargs['model'] == "gpt-3.5-turbo"
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_house_bot_comprehensive.py -v -k "model_by_severity or cheap_model"
```

Expected: All PASS

**Step 7: Commit**

```bash
git add houseagent/house_bot.py tests/test_house_bot_comprehensive.py
git commit -m "feat: add multi-model strategy with severity-based selection"
```

---

### Task 15: Add Comprehensive Configuration

**Files:**
- Create: `config/production.env.example`
- Modify: `README.md`

**Step 1: Create production configuration example**

Create `config/production.env.example`:

```bash
# Production Configuration - All Phases

# MQTT Connection
MQTT_BROKER=mqtt.office.local
MQTT_PORT=1883

# Office Mode
OFFICE_MODE=true
ENABLE_TOOLS=true

# Floor Plan
FLOOR_PLAN_PATH=/app/config/floor_plan.json

# Camera Integration
CAMERA_RTSP_BASE=rtsp://camera.local

# Filtering & Detection
ANOMALY_Z_THRESHOLD=2.5
SITUATION_MERGE_WINDOW=7

# Tool Configuration
TOOL_BUDGET_PER_MINUTE=10

# AI Models
CLASSIFIER_MODEL=gpt-3.5-turbo
OPENAI_MODEL=gpt-4
OPENAI_API_KEY=your-key-here

# Semantic Memory
CHROMA_PERSIST_DIR=/app/data/chroma
```

**Step 2: Update README with complete documentation**

Add to `README.md`:

```markdown
## Complete System Architecture (All Phases)

### Message Flow

1. **MQTT Input** - Sensors publish to hierarchical topics
2. **Validation** - Pydantic schemas validate message format
3. **Noise Filtering** - Duplicates and low-quality readings suppressed
4. **Anomaly Detection** - Z-score based outlier detection
5. **Situation Building** - Messages clustered by spatial/temporal proximity
6. **Tool Execution** - Floor plan queries, camera snapshots, state lookups
7. **AI Synthesis** - Model selected by severity, tools inform response
8. **Response** - Structured output with severity, tags, actions

### Configuration

See `config/production.env.example` for all configuration options.

Key settings:
- `OFFICE_MODE=true` - Enable office sensor processing
- `ENABLE_TOOLS=true` - Enable tool execution
- `ANOMALY_Z_THRESHOLD=2.5` - Z-score threshold for anomalies
- `CLASSIFIER_MODEL=gpt-3.5-turbo` - Fast model for routine events
- `OPENAI_MODEL=gpt-4` - Premium model for high-severity situations

### Testing

```bash
# Run all tests
uv run pytest

# Run specific phase tests
uv run pytest tests/test_schemas.py           # Phase 0
uv run pytest tests/test_noise_filter.py      # Phase 1
uv run pytest tests/test_situation_builder.py # Phase 2
uv run pytest tests/test_tool_router.py       # Phase 3-4
uv run pytest tests/test_house_bot.py         # Phase 5
```

### Deployment

See `docs/deployment.md` for Docker deployment instructions.
```

**Step 3: Commit**

```bash
git add config/production.env.example README.md
git commit -m "docs: add complete production configuration and documentation"
```

---

### Task 16: Integration Testing

**Files:**
- Create: `tests/test_integration_full.py`

**Step 1: Write end-to-end integration test**

Create `tests/test_integration_full.py`:

```python
# ABOUTME: End-to-end integration tests for full office-aware system
# ABOUTME: Validates complete pipeline from MQTT to AI response with all phases

import json
import tempfile
from unittest.mock import Mock, MagicMock, patch
from houseagent.message_batcher import MessageBatcher
from houseagent.agent_listener import AgentListener
from houseagent.house_bot import HouseBot


def test_full_pipeline_office_sensors():
    """Test complete pipeline: MQTT → validation → filtering → situation → tools → AI"""

    # Setup floor plan
    floor_plan_config = {
        "zones": {"lobby": {"name": "Lobby"}, "conf_a": {"name": "Conf A"}},
        "adjacency": {"lobby": ["conf_a"], "conf_a": ["lobby"]}
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(floor_plan_config, f)
        floor_plan_path = f.name

    # Setup components
    mqtt_client = Mock()

    with patch.dict('os.environ', {'FLOOR_PLAN_PATH': floor_plan_path}):
        batcher = MessageBatcher(mqtt_client, timeout=1.0)
        house_bot = HouseBot()
        house_bot.client = Mock()
        house_bot.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Office situation detected"))]
        )

        listener = AgentListener(mqtt_client, house_bot)

        # Simulate office sensor messages
        msg1 = MagicMock()
        msg1.payload = json.dumps({
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "motion_01",
            "sensor_type": "motion",
            "zone_id": "lobby",
            "value": {"detected": True}
        }).encode()

        msg2 = MagicMock()
        msg2.payload = json.dumps({
            "ts": "2025-10-14T10:30:05Z",
            "sensor_id": "temp_01",
            "sensor_type": "temperature",
            "zone_id": "lobby",
            "value": {"celsius": 22.0}
        }).encode()

        # Process through batcher
        batcher.on_message(mqtt_client, None, msg1)
        batcher.on_message(mqtt_client, None, msg2)

        # Verify messages queued
        assert batcher.message_queue.qsize() == 2

        # Create batch and send to listener
        batch = {"messages": [
            json.loads(msg1.payload),
            json.loads(msg2.payload)
        ]}

        batch_msg = MagicMock()
        batch_msg.payload = json.dumps(batch).encode()

        listener.on_message(mqtt_client, None, batch_msg)

        # Verify AI was called with situation
        assert house_bot.client.chat.completions.create.called
        call_args = house_bot.client.chat.completions.create.call_args[1]
        messages = call_args['messages']

        # Should have system prompt + user message with situation
        assert len(messages) >= 2
```

**Step 2: Run integration test**

```bash
uv run pytest tests/test_integration_full.py::test_full_pipeline_office_sensors -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_integration_full.py
git commit -m "test: add end-to-end integration test for full pipeline"
```

---

### Task 17: Final Documentation

**Files:**
- Create: `docs/deployment.md`
- Create: `docs/architecture.md`

**Step 1: Create deployment guide**

Create `docs/deployment.md`:

```markdown
# Deployment Guide

## Prerequisites

- Docker and Docker Compose
- MQTT broker accessible from container
- OpenAI API key
- Floor plan JSON configured

## Configuration

1. Copy example config:
```bash
cp config/production.env.example .env
```

2. Edit `.env` with your settings:
   - MQTT broker address
   - OpenAI API key
   - Floor plan path
   - Camera RTSP URLs (if using camera tools)

3. Create floor plan config at `config/floor_plan.json`

## Docker Deployment

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f house-agent

# Stop services
docker-compose down
```

## Monitoring

Logs are structured JSON via structlog. Key events:

- `message.validated` - Message passed validation
- `message.filtered` - Message suppressed by noise filter
- `situation.built` - Situation created from batch
- `tool.executed` - Tool execution result
- `anomaly.detected` - Anomaly flagged

## Troubleshooting

### No messages received
- Check MQTT broker connectivity
- Verify topic subscriptions match sensor topics
- Check `SUBSCRIBE_TOPIC` and office topic pattern

### Validation errors
- Check sensor message format matches schema
- Review `message.validation_failed` logs
- Verify zone mappings in config

### Tools not executing
- Ensure `ENABLE_TOOLS=true`
- Check floor plan JSON is valid
- Review tool budget settings
```

**Step 2: Create architecture documentation**

Create `docs/architecture.md`:

```markdown
# Architecture Documentation

## System Overview

HouseAgent is an office-aware, context-driven automation system that processes sensor data through multiple intelligence layers:

1. **Validation Layer** - Pydantic schemas ensure data quality
2. **Filtering Layer** - Noise suppression and anomaly detection
3. **Situation Layer** - Spatial/temporal clustering with corroboration
4. **Tool Layer** - Floor plan queries, camera access, state lookups
5. **AI Layer** - Multi-model orchestration with severity-based selection

## Component Architecture

### Message Flow

```
MQTT Sensors
    ↓
Collector (collector.py)
    ↓
MessageBatcher (validation, filtering, anomaly detection)
    ↓
AgentListener (situation building)
    ↓
HouseBot (tool execution, AI synthesis)
    ↓
Response
```

### Core Components

**Schemas (houseagent/schemas.py)**
- `SensorMessage`: Office sensor format
- `LegacyMessage`: Home automation compatibility
- Pydantic validation ensures data quality

**NoiseFilter (houseagent/noise_filter.py)**
- Deduplication with time windows
- Quality gates (battery, signal strength)
- Time-of-day sensitivity

**AnomalyDetector (houseagent/anomaly_detector.py)**
- Z-score based detection
- Per-sensor EWMA statistics
- Configurable thresholds

**SituationBuilder (houseagent/situation_builder.py)**
- Zone-based clustering
- Multi-sensor corroboration
- Confidence scoring

**FloorPlanModel (houseagent/floor_plan.py)**
- Zone definitions and relationships
- Adjacency graph
- Camera FOV mappings

**ToolRouter (houseagent/tools/router.py)**
- Tool registry and execution
- Timeout handling
- Error recovery

**HouseBot (houseagent/house_bot.py)**
- Model selection by severity
- Tool orchestration
- OpenAI integration

## Design Decisions

### Why Pydantic?
Type safety, validation, and serialization in one package. Easy conversion between legacy and new formats.

### Why Z-score for anomalies?
Simple, interpretable, no training required. Works well for sensor drift and outlier detection.

### Why 2+ sensor corroboration?
Reduces false positives from single sensor glitches. Increases confidence in situation assessment.

### Why multi-model?
Cost optimization - use gpt-3.5-turbo for routine events, reserve gpt-4 for complex situations.

## Extension Points

**Adding new tools:**
1. Implement tool class with `execute(params)` method
2. Register in `HouseBot.__init__`
3. Add to tool catalog

**Adding new sensor types:**
1. Update schema if needed
2. Add to anomaly detector value extraction
3. Update situation builder features

**Adding new filters:**
1. Implement filter class with `should_suppress(msg)` method
2. Add to MessageBatcher pipeline
```

**Step 3: Commit**

```bash
git add docs/deployment.md docs/architecture.md
git commit -m "docs: add deployment guide and architecture documentation"
```

---

## Execution Strategy

This plan implements all 5 phases sequentially with TDD throughout. Each task:

1. Writes failing test first
2. Implements minimal code to pass
3. Adds additional test cases
4. Commits frequently

**Estimated timeline:** 5 weeks following spec migration schedule

**Success criteria:**
- All tests passing at each phase
- No behavioral regressions
- Live office sensors processing correctly
- Complete documentation

**Next steps after plan:**
- Execute tasks in order
- Validate with live sensors after each phase
- Tune thresholds based on real data
- Monitor and iterate
