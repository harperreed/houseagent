import os
import paho.mqtt.client as mqtt
import logging
from dotenv import load_dotenv
import time
import structlog

from houseagent.agent_listener import AgentListener
from houseagent.handlers.camera_request_handler import CameraRequestHandler
from houseagent.floor_plan import FloorPlanModel

# Load configuration from .env file
load_dotenv()

# Set up basic logging configuration
logger = structlog.get_logger(__name__)


def on_connect(client, userdata, flags, reason_code, properties):
    """Handle MQTT connection (VERSION2 callback)"""
    logger.info("Connected to MQTT broker", reason_code=reason_code)
    topic = os.getenv("MESSAGE_BUNDLE_TOPIC", "your/input/topic/here")
    logger.debug(f"Subscribing to topic: {topic}")
    client.subscribe(topic)
    logger.info(f"Connected. Subscribed to topic: {topic}")

    # Subscribe camera request handler
    camera_handler.subscribe()


def on_message(client, userdata, msg):
    logger.info("Received message")
    logger.debug(f"Message: {msg.payload}")

    # Route camera request messages to camera handler
    if msg.topic == CameraRequestHandler.CAMERA_REQUEST_TOPIC:
        camera_handler.handle_request(msg.payload.decode("utf-8"))
    else:
        agent_client.on_message(client, userdata, msg)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Handle MQTT disconnection (VERSION2 callback)"""
    logger.info("mqtt.disconnected", reason_code=reason_code)
    if reason_code != 0:
        logger.error("mqtt.unexpected_disconnect", reason_code=reason_code)
        # Library handles automatic reconnection via reconnect_delay_set()


# Use configurable client ID to prevent collisions
client_id = os.getenv("MQTT_AGENT_CLIENT_ID", "housebot-agent")
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

# Initialize camera request handler
floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
floor_plan = FloorPlanModel.load(floor_plan_path)
camera_handler = CameraRequestHandler(floor_plan, client)

agent_client = AgentListener(client)

client.loop_start()

try:
    while not agent_client.stopped:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Shutting down...")
    agent_client.stop()

client.loop_stop()
client.disconnect()
