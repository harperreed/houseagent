# HouseBot

HouseBot is an AI-driven smart home assistant that notifies users about events happening in their house. The assistant receives updates about the house state through MQTT and uses the GPT-based ChatBot to generate human-readable, concise, and playful notifications. The notifications are sent back to the specified MQTT topic.

## Features

- Monitors house states and events
- Summarizes events in simple English
- Playful and user-friendly notifications
- MQTT-based communication

## Dependencies

- Python 3.x
- paho-mqtt
- chatgpt (GPT-based ChatBot)
- python-dotenv

## Setup

1. Install the required dependencies:

```
pip install paho-mqtt python-dotenv
```

2. Set up the required environment variables in a `.env` file:

```bash
MQTT_BROKER_ADDRESS=your_mqtt_broker_address
MQTT_PORT=your_mqtt_port_number
MQTT_KEEP_ALIVE_INTERVAL=your_mqtt_keep_alive_interval
TIMEOUT=batch_timeout_in_seconds
SUBSCRIBE_TOPIC=your_subscribe_topic
PUBLISH_TOPIC=your_publish_topic
```

3. Run the `housebot.py` script:

```bash
python housebot.py
```

## Usage

HouseBot monitors the specified MQTT topic for house state updates. When an update is received, it processes the message and generates a response using the ChatBot. The response is sent back to the specified MQTT topic as a notification. The program will continue running until manually interrupted.

## Structure

- `HouseBot` class: Handles the AI interaction using the ChatBot
- `MessageBatcher` class: Manages the batching and processing of incoming MQTT messages
- MQTT client setup: Handles the connection, subscription, and publishing to the MQTT broker
- Main loop: Runs the message processing and keeps the program running

## Phase 0: Foundation (Current)

The system now supports both legacy home automation messages and new hierarchical office sensor topics.

### New Topic Structure

Office sensors publish to: `office/{site}/{floor}/{zone}/{type}/{id}`

Example: `office/hq/1/conf_room_a/temperature/temp_01`

### Message Format

New format (Pydantic validated):
```json
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
```

Legacy format still supported (auto-converted).

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

See `.env.example` for all configuration options.

Key settings:
- `OFFICE_MODE=true` - Enable office sensor processing
- `ENABLE_TOOLS=true` - Enable tool execution
- `ANOMALY_Z_THRESHOLD=2.5` - Z-score threshold for anomalies
- `CLASSIFIER_MODEL=gpt-5-mini` - Fast GPT-5 model for routine events
- `SYNTHESIS_MODEL=gpt-5` - Premium GPT-5 model for high-severity situations
- `OPENAI_MODEL=gpt-5` - Default model (can use gpt-5, gpt-5-pro, gpt-5-codex)

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

## Customization

You can modify the `system_prompt` in the `HouseBot` class to change the AI's behavior or provide additional context. You can also adjust the `timeout` variable in the `.env` file to change the interval between message batches.

Remember to replace `your/input/topic/here` with the appropriate MQTT topics for your specific use case.

## Running Tests

To run the unit tests for HouseAgent:

1. Ensure you have installed the dependencies, including pytest
2. Navigate to the project root directory
3. Run the following command:

   ```
   pytest
   ```

This will discover and run all the tests in the `tests/` directory.

To generate a coverage report, run:

```
pytest --cov=houseagent tests/
```

This will show the test coverage for each file in the `houseagent/` directory.
