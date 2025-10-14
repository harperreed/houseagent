# ABOUTME: Real-time web dashboard for HouseAgent monitoring
# ABOUTME: Streams MQTT messages, AI responses, and system events via SSE

import os
import json
import time
from datetime import datetime
from collections import deque
from threading import Lock
from flask import Flask, render_template, Response, jsonify, request
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import structlog

load_dotenv()

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
logger = structlog.get_logger(__name__)

# Thread-safe message buffer
message_buffer = deque(maxlen=100)
buffer_lock = Lock()


def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to all relevant topics"""
    logger.info("Dashboard connected to MQTT", reason_code=reason_code)

    # Subscribe to sensor messages
    client.subscribe(os.getenv("SUBSCRIBE_TOPIC", "hassevents/notifications"))
    client.subscribe("office/+/+/+/+/+")

    # Subscribe to AI responses
    client.subscribe(os.getenv("NOTIFICATION_TOPIC", "houseevents/ai/publish"))

    # Subscribe to batched messages
    client.subscribe(os.getenv("MESSAGE_BUNDLE_TOPIC", "houseevents/ai/bundle/publish"))

    # Subscribe to camera events
    client.subscribe("office/+/+/+/camera/+")

    logger.info("Dashboard subscribed to all topics including cameras")


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages"""
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        payload = msg.payload.decode()

    event = {
        "timestamp": datetime.now().isoformat(),
        "topic": msg.topic,
        "payload": payload,
        "type": classify_message_type(msg.topic, payload),
    }

    with buffer_lock:
        message_buffer.append(event)
        logger.debug("Message buffered", topic=msg.topic, type=event["type"])


def classify_message_type(topic, payload):
    """Classify message type for display"""
    if "ai/publish" in topic and "bundle" not in topic:
        return "ai_response"
    elif "bundle" in topic:
        return "situation"
    elif "/camera/" in topic:
        return "camera"
    elif "office/" in topic:
        return "office_sensor"
    else:
        return "sensor"


# Create MQTT client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "dashboard")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Set up authentication if needed
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
if mqtt_username and mqtt_password:
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)

# Connect to broker
broker = os.getenv("MQTT_BROKER_ADDRESS", "localhost")
port = int(os.getenv("MQTT_PORT", 1883))
mqtt_client.connect(broker, port, 60)
mqtt_client.loop_start()

# Load floor plan for camera configuration
floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
with open(floor_plan_path) as f:
    floor_plan_data = json.load(f)
    app.config["CAMERAS"] = floor_plan_data.get("cameras", [])


@app.route("/")
def index():
    """Serve dashboard"""
    return render_template("dashboard.html")


@app.route("/api/messages")
def get_messages():
    """Get recent messages as JSON"""
    with buffer_lock:
        return jsonify(list(message_buffer))


@app.route("/stream")
def stream():
    """Server-Sent Events stream"""

    def event_stream():
        last_index = 0
        while True:
            with buffer_lock:
                current_messages = list(message_buffer)

            # Send new messages
            new_messages = current_messages[last_index:]
            for msg in new_messages:
                yield f"data: {json.dumps(msg)}\n\n"

            last_index = len(current_messages)
            time.sleep(0.5)  # Check for new messages every 500ms

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/camera/capture", methods=["POST"])
def camera_capture():
    """Trigger camera capture via MQTT request"""
    data = request.get_json()
    camera_id = data.get("camera_id")
    zone = data.get("zone")

    if not camera_id:
        return jsonify({"success": False, "error": "camera_id required"}), 400

    request_payload = {
        "camera_id": camera_id,
        "zone": zone,
        "timestamp": datetime.now().isoformat(),
        "source": "dashboard",
    }

    try:
        mqtt_client.publish("houseevents/camera/request", json.dumps(request_payload))
        logger.info("Camera capture requested", camera_id=camera_id)
        return jsonify({"success": True, "camera_id": camera_id})
    except Exception as e:
        logger.error("Failed to publish camera request", error=str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/camera/refresh_all", methods=["POST"])
def camera_refresh_all():
    """Trigger capture for all cameras"""
    cameras = app.config.get("CAMERAS", [])
    count = 0

    for camera in cameras:
        request_payload = {
            "camera_id": camera["id"],
            "zone": camera.get("zone"),
            "timestamp": datetime.now().isoformat(),
            "source": "dashboard_auto",
        }
        try:
            mqtt_client.publish(
                "houseevents/camera/request", json.dumps(request_payload)
            )
            count += 1
        except Exception as e:
            logger.error(
                "Failed to publish camera request", camera_id=camera["id"], error=str(e)
            )

    return jsonify({"success": True, "requested": count})


@app.route("/api/status")
def status():
    """System status"""
    return jsonify(
        {
            "mqtt_connected": mqtt_client.is_connected(),
            "buffer_size": len(message_buffer),
            "broker": broker,
            "timestamp": datetime.now().isoformat(),
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
