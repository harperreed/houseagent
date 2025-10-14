import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
import structlog
from houseagent.message_batcher import MessageBatcher

# Load configuration from .env file
load_dotenv()

logger = structlog.get_logger(__name__)


def on_connect(client, userdata, flags, rc):
    """Handle MQTT connection - subscribe to topics"""
    logger.info("mqtt.connected", result_code=rc)

    # Keep existing legacy subscription
    legacy_topic = os.getenv("SUBSCRIBE_TOPIC", "hassevents/notifications")
    client.subscribe(legacy_topic)
    logger.info("mqtt.subscribed", topic=legacy_topic)

    # Add hierarchical office topics
    office_pattern = "office/+/+/+/+/+"  # site/floor/zone/type/id
    client.subscribe(office_pattern)
    logger.info("mqtt.subscribed", topic=office_pattern, type="office")


def on_message(client, userdata, msg):
    logger.info("Received message")
    logger.debug(f"Message: {msg.payload}")
    message_batcher.on_message(client, userdata, msg)


def on_disconnect(client, userdata, rc):
    logger.info("Disconnected from MQTT broker")
    if rc != 0:
        logger.error(f"Unexpected disconnection. Result code: {rc}")


timeout = int(os.getenv("TIMEOUT", 60))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "housebot")
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

broker_address = os.getenv("MQTT_BROKER_ADDRESS", "localhost")
port_number = int(os.getenv("MQTT_PORT", 1883))
keep_alive_interval = int(os.getenv("MQTT_KEEP_ALIVE_INTERVAL", 60))

client.connect(broker_address, port_number, keep_alive_interval)
logger.debug(f"Connected to MQTT broker at {broker_address}:{port_number}")

message_batcher = MessageBatcher(client, timeout)

client.loop_start()

try:
    logger.info("Starting message batcher...")
    message_batcher.run()
except KeyboardInterrupt:
    logger.info("Shutting down...")
    message_batcher.stop()

client.loop_stop()
client.disconnect()

logging.info("Bye!")
