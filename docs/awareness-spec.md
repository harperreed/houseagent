# Delta Spec: Evolving HouseAgent to Office-Aware, Tool-Using System

## Overview
Transform the existing HouseAgent MQTT automation system into a context-aware, tool-using platform for office sensor monitoring while preserving the core architecture and extending its capabilities.

---

## Current State Assessment

**What We Keep:**
- MQTT broker integration with paho-mqtt
- Message batching pipeline (`MessageBatcher`)
- Agent listener pattern (`AgentListener`)
- OpenAI integration for response generation
- Semantic memory with ChromaDB
- Docker-based deployment
- Structlog-based observability

**What We Enhance:**
- Topic structure (flat → hierarchical)
- Message validation (basic JSON → Pydantic schemas)
- Batching logic (time-only → situation-aware aggregation)
- AI responses (personality-only → structured JSON + tools)
- Memory system (semantic-only → semantic + spatial + temporal)

**What We Add:**
- Noise filtering & anomaly detection
- Floor plan model & spatial reasoning
- Tool-calling framework
- Situation builder
- Multi-model orchestration
- RTSP camera integration

---

## Phase 0: Foundation Changes (Keep Everything Working)

### 0.1 Schema Evolution
Extend current message format while maintaining backward compatibility:

```python
# houseagent/schemas.py (NEW FILE)
from pydantic import BaseModel
from typing import Optional, Dict, Any

class LegacyMessage(BaseModel):
    """Current format - keep working"""
    sensor: Optional[str]
    value: Optional[Any]
    room: Optional[str]

class SensorMessage(BaseModel):
    """Enhanced format for new sensors"""
    ts: str  # ISO8601
    sensor_id: str
    sensor_type: str
    zone_id: str
    site_id: str = "hq"
    floor: int = 1
    value: Dict[str, Any]
    quality: Optional[Dict[str, Any]]

    @classmethod
    def from_legacy(cls, msg: Dict, zone_map: Dict):
        """Convert legacy to new format"""
        return cls(
            ts=datetime.now().isoformat(),
            sensor_id=msg.get("sensor", "unknown"),
            sensor_type=msg.get("sensor", "unknown"),
            zone_id=zone_map.get(msg.get("room"), "unknown"),
            value={"reading": msg.get("value")}
        )
```

### 0.2 Topic Migration
Support both old and new topic structures:

```python
# In collector.py on_connect():
def on_connect(client, userdata, flags, rc):
    # Keep existing subscription
    legacy_topic = os.getenv('SUBSCRIBE_TOPIC', 'hassevents/notifications')
    client.subscribe(legacy_topic)

    # Add new hierarchical topics
    office_pattern = "office/+/+/+/+/+"  # site/floor/zone/type/id
    client.subscribe(office_pattern)
```

---

## Phase 1: Noise Filtering & Validation Layer

### 1.1 Enhanced MessageBatcher
```python
# houseagent/message_batcher.py - MODIFY
class MessageBatcher:
    def __init__(self, client, timeout):
        # ... existing init ...
        self.validator = MessageValidator()  # NEW
        self.noise_filter = NoiseFilter()    # NEW
        self.anomaly_detector = AnomalyDetector()  # NEW

    def on_message(self, client, userdata, msg):
        # Existing JSON decode
        message = json.loads(msg.payload)

        # NEW: Validate & filter
        if sensor_msg := self.validator.validate(message):
            if not self.noise_filter.should_suppress(sensor_msg):
                if self.anomaly_detector.is_anomalous(sensor_msg):
                    sensor_msg.anomaly_score = self.anomaly_detector.score
                self.message_queue.put(sensor_msg.dict())
```

### 1.2 New NoiseFilter Component
```python
# houseagent/noise_filter.py (NEW)
class NoiseFilter:
    def __init__(self):
        self.dedup_window = {}  # sensor_id -> (value, timestamp)
        self.ewma = {}  # zone/sensor -> (mean, variance)

    def should_suppress(self, msg: SensorMessage) -> bool:
        # Deduplication
        if self._is_duplicate(msg):
            return True

        # Quality gates
        if msg.quality and msg.quality.get('battery_pct', 100) < 5:
            return True

        # Time-of-day sensitivity
        if self._is_working_hours() and msg.sensor_type == 'motion':
            return random.random() > 0.3  # Lower sensitivity

        return False
```

---

## Phase 2: Situation Building (Replaces Simple Batching)

### 2.1 Evolve AgentListener to Situation Processor
```python
# houseagent/agent_listener.py - MODIFY
class AgentListener:
    def __init__(self, client, ...):
        # ... existing init ...
        self.situation_builder = SituationBuilder()  # NEW
        self.floor_plan = FloorPlanModel.load()     # NEW

    def on_message(self, client, userdata, msg):
        batch = json.loads(msg.payload)

        # NEW: Build situation instead of raw batch
        situation = self.situation_builder.build(
            batch['messages'],
            self.floor_plan
        )

        if situation.requires_response():
            # Continue with existing flow but with situation
            response = self.house_bot.generate_response(
                situation.to_prompt_json(),
                self.last_situation,
                self.message_history
            )
```

### 2.2 New Situation Builder
```python
# houseagent/situation_builder.py (NEW)
class SituationBuilder:
    def build(self, messages: List[Dict], floor_plan: FloorPlanModel):
        # Group by zone cluster
        zone_clusters = self._cluster_by_zone(messages, floor_plan)

        # Compute features
        features = {
            'event_counts': Counter([m['sensor_type'] for m in messages]),
            'zones': list(zone_clusters.keys()),
            'anomaly_scores': [m.get('anomaly_score', 0) for m in messages]
        }

        # Cross-sensor corroboration
        if self._has_corroboration(messages):
            return Situation(
                id=f"sit-{ulid.new()}",
                messages=messages,
                features=features,
                confidence=0.8
            )
        return None
```

---

## Phase 3: Tool-Calling Framework

### 3.1 Modify HouseBot for Tools
```python
# houseagent/house_bot.py - MODIFY
class HouseBot:
    def __init__(self):
        # ... existing init ...
        self.tool_router = ToolRouter()  # NEW
        self.tool_policy = ToolPolicy()  # NEW

    def generate_response(self, current_state, last_state, message_history=None):
        # Existing message building...

        # NEW: Add tool capability
        messages[0]['content'] += "\n\nAvailable tools: " + self.tool_router.get_catalog()

        # First pass: Determine needed tools
        tool_request = self._get_tool_requirements(messages)

        if tool_request and self.tool_policy.approve(tool_request):
            tool_results = self.tool_router.execute(tool_request)
            messages.append({
                "role": "assistant",
                "content": f"Tool results: {json.dumps(tool_results)}"
            })

        # Continue with existing OpenAI call
        response = self.client.chat.completions.create(...)
```

### 3.2 New Tool Router
```python
# houseagent/tools/router.py (NEW)
class ToolRouter:
    def __init__(self):
        self.tools = {
            'get_camera_snapshot': CameraTool(),
            'floor_plan_query': FloorPlanTool(),
            'get_recent_state': StateTool(),
            'similar_situations': self._similarity_search
        }

    def execute(self, request: ToolRequest) -> Dict:
        tool = self.tools.get(request.tool_name)
        if not tool:
            return {"error": "Unknown tool"}

        # Execute with timeout and error handling
        try:
            return timeout(5)(tool.execute)(request.params)
        except TimeoutError:
            return {"error": "Tool timeout"}
```

---

## Phase 4: Floor Plan Integration

### 4.1 Floor Plan Model
```python
# houseagent/floor_plan.py (NEW)
class FloorPlanModel:
    def __init__(self, config_path="floor_plan.json"):
        self.zones = {}
        self.sensors = {}
        self.adjacency = {}

    def get_adjacent_zones(self, zone_id: str) -> List[str]:
        return self.adjacency.get(zone_id, [])

    def get_cameras_for_zone(self, zone_id: str) -> List[str]:
        return [
            cam['camera_id'] for cam in self.cameras
            if self._overlaps(cam['fov_polygon'], self.zones[zone_id]['polygon'])
        ]
```

### 4.2 Integrate with Existing Semantic Memory
```python
# houseagent/semantic_memory.py - MODIFY
class SemanticMemory:
    def __init__(self, ...):
        # ... existing init ...
        self.floor_plan = FloorPlanModel.load()  # NEW

    def add_message(self, message, role="user", message_id=None):
        # Existing embedding logic...

        # NEW: Add spatial metadata
        if zone_id := message.get('zone_id'):
            metadata['zone_id'] = zone_id
            metadata['adjacent_zones'] = self.floor_plan.get_adjacent_zones(zone_id)
```

---

## Phase 5: Multi-Model Strategy

### 5.1 Enhance Model Selection
```python
# houseagent/house_bot.py - MODIFY
class HouseBot:
    def __init__(self):
        # ... existing init ...
        self.classifier_model = "gpt-3.5-turbo"  # Fast, cheap
        self.synthesis_model = os.getenv("OPENAI_MODEL", "gpt-4")

    def generate_response(self, ...):
        # Classify situation severity first
        severity = self._classify_severity(current_state)

        model = self.synthesis_model if severity > 0.7 else self.classifier_model

        # Add structured output for high-severity
        if severity > 0.7:
            messages.append({
                "role": "system",
                "content": "Respond with both text AND JSON: {severity, tags, actions}"
            })
```

---

## Migration Strategy

### Week 1: Schema & Validation
1. Add Pydantic schemas alongside existing code
2. Deploy validator in "log-only" mode
3. Update prompts directory structure

### Week 2: Noise Filtering
1. Add NoiseFilter to MessageBatcher
2. Deploy with conservative thresholds
3. Monitor suppression rates

### Week 3: Situation Building
1. Parallel-run situation builder
2. A/B test situation vs raw batches
3. Gradually increase situation usage

### Week 4: Tools & Floor Plan
1. Deploy read-only tools first
2. Add floor plan config file
3. Enable tool calling for specific topics

### Week 5: Production Hardening
1. Add comprehensive metrics
2. Implement rate limiting
3. Deploy multi-model routing

---

## Configuration Changes

### New Environment Variables
```bash
# .env additions
OFFICE_MODE=true
ENABLE_TOOLS=true
FLOOR_PLAN_PATH=/app/config/floor_plan.json
CAMERA_RTSP_BASE=rtsp://camera.local
ANOMALY_Z_THRESHOLD=2.5
SITUATION_MERGE_WINDOW=7
TOOL_BUDGET_PER_MINUTE=10
CLASSIFIER_MODEL=gpt-3.5-turbo
```

### Docker Compose Updates
```yaml
services:
  house-agent:
    volumes:
      - ./config/floor_plan.json:/app/config/floor_plan.json
      - ./skills:/app/skills  # For tool definitions
    environment:
      - OFFICE_MODE=${OFFICE_MODE}
```

---

## Testing Strategy

1. **Compatibility Tests**: Ensure legacy messages still work
2. **Tool Tests**: Mock tool execution with various scenarios
3. **Integration Tests**: Full pipeline with situations + tools
