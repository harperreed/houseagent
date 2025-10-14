import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
import structlog
from houseagent.message_batcher import MessageBatcher

# Load configuration from .env file
load_dotenv()

logger = structlog.get_logger(__name__)


def on_connect(client, userdata, flags, reason_code, properties):
    """Handle MQTT connection - subscribe to topics (VERSION2 callback)"""
    logger.info("mqtt.connected", reason_code=reason_code)

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


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Handle MQTT disconnection (VERSION2 callback)"""
    logger.info("mqtt.disconnected", reason_code=reason_code)
    if reason_code != 0:
        logger.error("mqtt.unexpected_disconnect", reason_code=reason_code)
        # Library handles automatic reconnection via reconnect_delay_set()


timeout = int(os.getenv("TIMEOUT", 60))

# Use configurable client ID to prevent collisions
client_id = os.getenv("MQTT_COLLECTOR_CLIENT_ID", "housebot-collector")
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Enable automatic reconnection with exponential backoff
client.reconnect_delay_set(min_delay=1, max_delay=120)

# Set up authentication if credentials are provided
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
if mqtt_username and mqtt_password:
    client.username_pw_set(mqtt_username, mqtt_password)
    logger.info("mqtt.auth_configured", username=mqtt_username)

broker_address = os.getenv("MQTT_BROKER_ADDRESS", "localhost")
port_number = int(os.getenv("MQTT_PORT", 1883))
keep_alive_interval = int(os.getenv("MQTT_KEEP_ALIVE_INTERVAL", 60))

logger.info(
    "mqtt.connecting",
    broker=broker_address,
    port=port_number,
    keepalive=keep_alive_interval,
)
client.connect(broker_address, port_number, keep_alive_interval)
logger.info("mqtt.connect_initiated")

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
