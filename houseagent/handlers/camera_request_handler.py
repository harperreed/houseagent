# ABOUTME: MQTT handler for dashboard camera capture requests
# ABOUTME: Captures snapshots via CameraTool and publishes office sensor events

import json
import base64
import structlog
from houseagent.floor_plan import FloorPlanModel
from houseagent.tools.camera_tool import CameraTool


class CameraRequestHandler:
    """Handles camera capture requests from dashboard via MQTT"""

    CAMERA_REQUEST_TOPIC = "houseevents/camera/request"

    def __init__(self, floor_plan: FloorPlanModel, mqtt_client):
        self.logger = structlog.get_logger(__name__)
        self.floor_plan = floor_plan
        self.mqtt_client = mqtt_client
        self.camera_tool = CameraTool(floor_plan)

    def subscribe(self):
        """Subscribe to camera request topic"""
        self.mqtt_client.subscribe(self.CAMERA_REQUEST_TOPIC)
        self.logger.info(
            "Subscribed to camera requests", topic=self.CAMERA_REQUEST_TOPIC
        )

    def handle_request(self, payload: str):
        """Process camera capture request and publish office sensor event"""
        try:
            request = json.loads(payload)
            camera_id = request.get("camera_id")

            # Find camera in floor plan
            camera = next(
                (c for c in self.floor_plan.cameras if c["id"] == camera_id), None
            )
            if not camera:
                self.logger.warning("Invalid camera_id", camera_id=camera_id)
                return

            # Execute camera capture
            result = self.camera_tool.execute({"camera_id": camera_id})

            if not result.get("success"):
                self.logger.error(
                    "Camera capture failed",
                    camera_id=camera_id,
                    error=result.get("error"),
                )
                return

            # Load and encode image
            with open(result["snapshot_path"], "rb") as f:
                image_data = f.read()
            image_base64 = (
                f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"
            )

            # Build office sensor event
            zone = camera.get("zone", "unknown")
            floor = self.floor_plan.zones.get(zone, {}).get("floor", 1)
            topic = f"office/default/{floor}/{zone}/camera/{camera_id}"

            event = {
                "entity_id": f"camera.{camera_id}",
                "state": "snapshot_captured",
                "attributes": {
                    "zone": zone,
                    "camera_name": camera.get("name", camera_id),
                    "image_base64": image_base64,
                    "vision_analysis": result.get("analysis", ""),
                    "timestamp": request.get("timestamp"),
                    "snapshot_path": result["snapshot_path"],
                },
            }

            # Publish to office sensor topic
            self.mqtt_client.publish(topic, json.dumps(event))
            self.logger.info(
                "Camera snapshot published", camera_id=camera_id, topic=topic
            )

        except Exception as e:
            self.logger.error("Failed to handle camera request", error=str(e))
