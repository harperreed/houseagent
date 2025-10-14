import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path to import web_dashboard
sys.path.insert(0, str(Path(__file__).parent.parent))
from web_dashboard import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_camera_capture_endpoint(client):
    """Test /api/camera/capture publishes MQTT request"""
    with patch("web_dashboard.mqtt_client") as mock_mqtt:
        response = client.post(
            "/api/camera/capture",
            json={"camera_id": "front_entrance", "zone": "entryway"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

        # Verify MQTT publish called
        assert mock_mqtt.publish.called
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == "houseevents/camera/request"


def test_camera_refresh_all_endpoint(client):
    """Test /api/camera/refresh_all publishes requests for all cameras"""
    with patch("web_dashboard.mqtt_client") as mock_mqtt:
        with patch("web_dashboard.app") as mock_app:
            # Mock floor plan with 2 cameras
            mock_app.config = {
                "CAMERAS": [
                    {"id": "cam1", "zone": "zone1"},
                    {"id": "cam2", "zone": "zone2"},
                ]
            }

            response = client.post("/api/camera/refresh_all")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["requested"] == 2

            # Should publish 2 requests
            assert mock_mqtt.publish.call_count == 2
