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
