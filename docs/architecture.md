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
