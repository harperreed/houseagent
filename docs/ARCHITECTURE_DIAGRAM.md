# HouseAgent Architecture Diagram

## Overview

The `architecture.dot` file provides a comprehensive visual representation of the HouseAgent system architecture, showing all components, data flows, and interactions.

## Generated Files

- **architecture.dot** - GraphViz source file
- **architecture.png** - High-resolution PNG (4344x3013, 755KB)
- **architecture.svg** - Scalable SVG (68KB, best for web viewing)

## How to Regenerate

```bash
# PNG version
dot -Tpng docs/architecture.dot -o docs/architecture.png

# SVG version
dot -Tsvg docs/architecture.dot -o docs/architecture.svg

# PDF version
dot -Tpdf docs/architecture.dot -o docs/architecture.pdf
```

## Architecture Layers

### 1. **External Systems** (Top)
- **MQTT Broker**: Mosquitto message broker for pub/sub
- **Sensors**: Office hierarchical sensors + Home Assistant legacy sensors
- **OpenAI APIs**: Three model tiers
  - GPT-5-mini: Fast classifier for routine events & notification filtering
  - GPT-5: Premium synthesis for high-severity situations
  - GPT-5 Vision: Camera snapshot analysis
- **RTSP Cameras**: 7 security cameras with vision analysis

### 2. **Data Ingestion Layer**
- **Collector**: Subscribes to both legacy and hierarchical MQTT topics
- Dual-mode operation for backward compatibility

### 3. **Processing Pipeline**
- **Validation**: Pydantic schemas (SensorMessage, LegacyMessage)
- **MessageBatcher**: Time-based batching with validation coordination
- **NoiseFilter**: Deduplication, quality gates, time-of-day sensitivity
- **AnomalyDetector**: Z-score detection with EWMA statistics

### 4. **Intelligence Layer**
- **AgentListener**: Orchestrates situation building and response generation
- **SituationBuilder**:
  - Zone-based clustering
  - Multi-sensor corroboration
  - Confidence scoring with ULID generation
- **Should Respond Filter**:
  - GPT-5-mini decision gate
  - JSON structured output
  - Prevents notification spam
- **HouseBot**:
  - Multi-model selection by severity
  - Tool orchestration
  - Prompt injection

### 5. **Tool Framework**
- **ToolRouter**: Registry with timeout handling and error recovery
- **FloorPlanTool**: Zone queries (adjacent_zones, zone_info)
- **CameraTool**:
  - RTSP snapshot capture
  - GPT-5 Vision analysis
  - Zone/camera lookup

### 6. **Knowledge & State**
- **FloorPlanModel**: Zone definitions, adjacency graph, camera FOV mappings
- **SemanticMemory**: ChromaDB vector store with temporal windowing
- **ChromaDB**: Persistent vector storage for message history

### 7. **Configuration**
- **Prompts Directory**:
  - housebot_system.txt
  - housebot_human.txt
  - should_respond_filter.txt
  - camera_vision.txt
- **floor_plan.json**: Zone polygons, sensor placement, camera FOVs
- **.env Configuration**: MQTT settings, OpenAI models, feature flags

### 8. **Web Dashboard**
- **Flask Backend**: SSE streaming on port 5001
- **Dashboard UI**: Real-time panels with color coding
  - 🟣 Magenta: GlaDOS Responses
  - 🔵 Cyan: Situations
  - 🟡 Yellow: Sensors
  - 🟢 Green: All Events
  - 💜 Purple: Camera Snapshots
- **CameraRequestHandler**: Manual camera triggers with MQTT publishing

### 9. **Output Layer**
- **NOTIFICATION_TOPIC**: AI responses (GlaDOS wit)
- **MESSAGE_BUNDLE_TOPIC**: Situation bundles
- **Camera Topics**: office/.../camera/{id} for snapshot analysis

## Key Data Flows

### Primary Pipeline (Happy Path)
```
Office Sensors → MQTT Broker → Collector → MessageBatcher
  → (Validation, Filtering, Anomaly Detection)
  → AgentListener → SituationBuilder
  → Should Respond Filter (GPT-5-mini)
  → HouseBot (GPT-5/GPT-5-mini)
  → NOTIFICATION_TOPIC
```

### Tool Execution Flow
```
HouseBot → ToolRouter → [FloorPlanTool | CameraTool]
CameraTool → RTSP Camera → GPT-5 Vision → Analysis
FloorPlanTool → FloorPlanModel → Zone Data
Tool Results → HouseBot (injected into prompt)
```

### Filter Gate (Spam Prevention)
```
AgentListener → Should Respond Filter → GPT-5-mini
  → JSON: {should_respond: true/false, reason: "..."}
  → If NO: Skip response (save API costs)
  → If YES: Continue to HouseBot
```

### Web Dashboard Flow
```
MQTT Broker → Web Dashboard (SSE) → Dashboard UI
Dashboard UI → Camera Handler → Camera Tool → Camera Topic → MQTT Broker
```

## Color Coding

- **Blue tones**: Sensors and external data sources
- **Green tones**: Ingestion and processing
- **Yellow/Gold**: Filtering and detection
- **Cyan/Teal**: Situation building
- **Purple/Magenta**: AI and tool execution
- **Pink**: Camera and vision processing
- **Red**: OpenAI synthesis models
- **Gray**: Configuration and static data

## Edge Styles

- **Solid lines**: Primary data flow
- **Dashed lines**: Responses/return values
- **Dotted lines**: Configuration loading
- **Thicker lines (penwidth=2)**: Main pipeline paths

## Component Shapes

- **Rectangles**: Processing components
- **Cylinders**: Data stores
- **Diamonds**: Decision gates
- **3D Boxes**: Physical sensors/cameras
- **Components**: External APIs
- **Folders**: File-based config
- **Notes**: Configuration files
- **Parallelograms**: MQTT topics (output)

## Understanding the System

### Backward Compatibility
The system maintains dual-mode operation:
- Legacy topic: `hassevents/notifications`
- Hierarchical topic: `office/{site}/{floor}/{zone}/{type}/{id}`
- Auto-conversion from LegacyMessage to SensorMessage

### Multi-Model Intelligence
- **Classifier (GPT-5-mini)**: Fast, cheap, routine events (severity < 0.7)
- **Synthesizer (GPT-5)**: Slow, expensive, complex situations (severity > 0.7)
- **Vision (GPT-5)**: Camera snapshot analysis on-demand

### Spam Prevention
The Should Respond Filter (GPT-5-mini) acts as a gate:
- **Responds YES for**: Multiple correlated events, unusual patterns, anomalies, safety concerns
- **Responds NO for**: Single routine readings, normal activity, repetitive patterns
- **Saves costs**: Most boring events filtered by cheap model before expensive synthesis

### Situation Building
Instead of simple time-based batching:
1. Clusters messages by spatial proximity (adjacent zones)
2. Requires 2+ sensors for corroboration
3. Computes confidence score
4. Generates unique ULID for tracking
5. Only high-confidence situations proceed to AI

### Tool Framework
Tools augment AI responses with real-time data:
- **FloorPlanTool**: "What zones are adjacent to hack_area?"
- **CameraTool**: "Show me a snapshot of the kitchen"
- Tool results injected into prompt context
- 5-second timeout with error recovery

## Testing the Diagram

The diagram is validated and renders successfully:
- ✅ Valid GraphViz syntax
- ✅ PNG generation: 755KB, 4344x3013 pixels
- ✅ SVG generation: 68KB (scalable)
- ✅ All components represented
- ✅ All data flows documented

## Future Enhancements

Potential additions to the architecture:
- [ ] State machine for conversation context
- [ ] Multi-site support with site-level aggregation
- [ ] Historical playback for situation debugging
- [ ] A/B testing framework for prompts
- [ ] Rate limiting and cost tracking dashboard
- [ ] WebSocket support for bidirectional communication

## Related Documentation

- `docs/architecture.md` - Detailed component descriptions
- `docs/awareness-spec.md` - Original delta specification
- `README.md` - System overview and setup
- `README_DASHBOARD.md` - Web dashboard guide
