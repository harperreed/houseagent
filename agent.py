import os
import json
import paho.mqtt.client as mqtt
import logging
from dotenv import load_dotenv
import time
import structlog

from houseagent.agent_listener import AgentListener

# Load configuration from .env file
load_dotenv()

# Set up basic logging configuration
# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Define a processor function
def processor(_, __, event_dict):
    event_dict['message'] = event_dict.get('event')
    return event_dict

# Configure structlog to interoperate with logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def on_connect(client, userdata, flags, rc):
    logger.info("Connected to MQTT broker")
    topic = os.getenv('MESSAGE_BUNDLE_TOPIC', 'your/input/topic/here')
    logger.debug(f"Subscribing to topic: {topic}")
    client.subscribe(topic)
    logger.info(f"Connected with result code {rc}. Subscribed to topic: {topic}")

def on_message(client, userdata, msg):
    logger.info("Received message")
    logger.debug(f"Message: {msg.payload}")
    agent_client.on_message(client, userdata, msg)

def on_disconnect(client, userdata, rc):
    logger.info("Disconnected from MQTT broker")
    if rc != 0:
        logger.error(f"Unexpected disconnection. Result code: {rc}")
  

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
port_number = int(os.getenv('MQTT_PORT', 1883))
keep_alive_interval = int(os.getenv('MQTT_KEEP_ALIVE_INTERVAL', 120))

client.connect(broker_address, port_number, keep_alive_interval)
logging.debug(f"Connected to MQTT broker at {broker_address}:{port_number}")

agent_client = AgentListener(client)

client.loop_start()

try:
    while not agent_client.stopped:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Shutting down...")
    agent_client.stop()

client.loop_stop()
client.disconnect
