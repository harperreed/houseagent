"""Integration test for camera dashboard feature"""

import json
from unittest.mock import Mock, patch


def test_end_to_end_camera_flow():
    """Test complete flow: dashboard request → agent capture → dashboard receive"""

    # 1. Simulate dashboard publishing request
    dashboard_mqtt = Mock()

    request_payload = {
        "camera_id": "front_entrance",
        "zone": "entryway",
        "timestamp": "2025-10-14T12:00:00Z",
        "source": "dashboard",
    }

    # Dashboard would publish this request
    dashboard_mqtt.publish("houseevents/camera/request", json.dumps(request_payload))
    assert dashboard_mqtt.publish.called
    assert dashboard_mqtt.publish.call_args[0][0] == "houseevents/camera/request"

    # 2. Agent receives and processes
    from houseagent.handlers.camera_request_handler import CameraRequestHandler
    from houseagent.floor_plan import FloorPlanModel

    floor_plan = FloorPlanModel("config/floor_plan.json")
    agent_mqtt = Mock()
    handler = CameraRequestHandler(floor_plan, agent_mqtt)

    with patch("houseagent.tools.camera_tool.CameraTool.execute") as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "camera_id": "front_entrance",
            "zone": "entryway",
            "analysis": "Test analysis",
            "snapshot_path": "/tmp/test.jpg",
        }

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b"test_data"
            )

            handler.handle_request(json.dumps(request_payload))

    # 3. Verify agent published office sensor event
    assert agent_mqtt.publish.called
    topic = agent_mqtt.publish.call_args[0][0]
    assert topic == "office/default/1/entryway/camera/front_entrance"

    payload = json.loads(agent_mqtt.publish.call_args[0][1])
    assert payload["entity_id"] == "camera.front_entrance"
    assert "image_base64" in payload["attributes"]
    assert payload["attributes"]["vision_analysis"] == "Test analysis"

    # 4. Verify the complete flow
    # Dashboard receives this event on the subscribed topic and displays it
    assert payload["state"] == "snapshot_captured"
    assert payload["attributes"]["zone"] == "entryway"
    assert "camera_name" in payload["attributes"]
