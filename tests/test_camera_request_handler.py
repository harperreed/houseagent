import json
from unittest.mock import Mock, patch
from houseagent.handlers.camera_request_handler import CameraRequestHandler
from houseagent.floor_plan import FloorPlanModel


def test_camera_request_handler_valid_request():
    """Test handler processes valid camera request and publishes office sensor event"""
    floor_plan = FloorPlanModel.load("config/floor_plan.json")
    mqtt_client = Mock()
    handler = CameraRequestHandler(floor_plan, mqtt_client)

    request_payload = json.dumps(
        {
            "camera_id": "front_entrance",
            "zone": "entryway",
            "timestamp": "2025-10-14T12:00:00Z",
            "source": "dashboard",
        }
    )

    with patch("houseagent.tools.camera_tool.CameraTool.execute") as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "camera_id": "front_entrance",
            "zone": "entryway",
            "analysis": "Two people entering",
            "snapshot_path": "/tmp/test.jpg",
        }

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b"fake_image_data"
            )

            handler.handle_request(request_payload)

    # Verify MQTT publish called with office sensor format
    assert mqtt_client.publish.called
    topic = mqtt_client.publish.call_args[0][0]
    assert topic == "office/default/1/entryway/camera/front_entrance"

    payload = json.loads(mqtt_client.publish.call_args[0][1])
    assert payload["entity_id"] == "camera.front_entrance"
    assert payload["state"] == "snapshot_captured"
    assert "image_base64" in payload["attributes"]


def test_camera_request_handler_invalid_camera():
    """Test handler ignores invalid camera_id"""
    floor_plan = FloorPlanModel.load("config/floor_plan.json")
    mqtt_client = Mock()
    handler = CameraRequestHandler(floor_plan, mqtt_client)

    request_payload = json.dumps(
        {
            "camera_id": "nonexistent",
            "zone": "nowhere",
            "timestamp": "2025-10-14T12:00:00Z",
        }
    )

    handler.handle_request(request_payload)

    # Should not publish anything for invalid camera
    assert not mqtt_client.publish.called
