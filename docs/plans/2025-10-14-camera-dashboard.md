# Camera Dashboard Implementation Plan

> **For Claude:** Use `${SUPERPOWERS_SKILLS_ROOT}/skills/collaboration/executing-plans/SKILL.md` to implement this plan task-by-task.

**Goal:** Add camera snapshot panel to dashboard with MQTT-driven auto-refresh and manual capture, publishing camera events to office sensor topics for AI analysis.

**Architecture:** MQTT request/response pattern where dashboard publishes camera capture requests, agent handles via existing CameraTool and publishes office sensor events with base64 images, dashboard displays via SSE stream. Auto-refresh every 60s, manual per-camera capture available.

**Tech Stack:** Flask, paho-mqtt, existing CameraTool (ffmpeg + GPT-5 vision), JavaScript SSE, base64 image encoding

---

## Task 1: Camera Request Handler (Agent Side)

**Files:**
- Create: `houseagent/handlers/camera_request_handler.py`
- Modify: `houseagent/house_bot.py` (register handler)
- Test: `tests/test_camera_request_handler.py`

**Step 1: Write failing test for camera request handler**

Create `tests/test_camera_request_handler.py`:

```python
import json
import pytest
from unittest.mock import Mock, patch
from houseagent.handlers.camera_request_handler import CameraRequestHandler
from houseagent.floor_plan import FloorPlanModel


def test_camera_request_handler_valid_request():
    """Test handler processes valid camera request and publishes office sensor event"""
    floor_plan = FloorPlanModel.from_file("config/floor_plan.json")
    mqtt_client = Mock()
    handler = CameraRequestHandler(floor_plan, mqtt_client)

    request_payload = json.dumps({
        "camera_id": "front_entrance",
        "zone": "entryway",
        "timestamp": "2025-10-14T12:00:00Z",
        "source": "dashboard"
    })

    with patch('houseagent.tools.camera_tool.CameraTool.execute') as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "camera_id": "front_entrance",
            "zone": "entryway",
            "analysis": "Two people entering",
            "snapshot_path": "/tmp/test.jpg"
        }

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake_image_data'

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
    floor_plan = FloorPlanModel.from_file("config/floor_plan.json")
    mqtt_client = Mock()
    handler = CameraRequestHandler(floor_plan, mqtt_client)

    request_payload = json.dumps({
        "camera_id": "nonexistent",
        "zone": "nowhere",
        "timestamp": "2025-10-14T12:00:00Z"
    })

    handler.handle_request(request_payload)

    # Should not publish anything for invalid camera
    assert not mqtt_client.publish.called
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_camera_request_handler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'houseagent.handlers.camera_request_handler'"

**Step 3: Write minimal implementation**

Create `houseagent/handlers/camera_request_handler.py`:

```python
# ABOUTME: MQTT handler for dashboard camera capture requests
# ABOUTME: Captures snapshots via CameraTool and publishes office sensor events

import json
import base64
import structlog
from typing import Optional
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
        self.logger.info("Subscribed to camera requests", topic=self.CAMERA_REQUEST_TOPIC)

    def handle_request(self, payload: str):
        """Process camera capture request and publish office sensor event"""
        try:
            request = json.loads(payload)
            camera_id = request.get("camera_id")

            # Find camera in floor plan
            camera = next((c for c in self.floor_plan.cameras if c["id"] == camera_id), None)
            if not camera:
                self.logger.warning("Invalid camera_id", camera_id=camera_id)
                return

            # Execute camera capture
            result = self.camera_tool.execute({"camera_id": camera_id})

            if not result.get("success"):
                self.logger.error("Camera capture failed", camera_id=camera_id, error=result.get("error"))
                return

            # Load and encode image
            with open(result["snapshot_path"], "rb") as f:
                image_data = f.read()
            image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"

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
                    "snapshot_path": result["snapshot_path"]
                }
            }

            # Publish to office sensor topic
            self.mqtt_client.publish(topic, json.dumps(event))
            self.logger.info("Camera snapshot published", camera_id=camera_id, topic=topic)

        except Exception as e:
            self.logger.error("Failed to handle camera request", error=str(e))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_camera_request_handler.py -v`
Expected: PASS (2 tests)

**Step 5: Register handler in HouseBot**

Modify `houseagent/house_bot.py` to import and register the handler:

```python
# Add import at top
from houseagent.handlers.camera_request_handler import CameraRequestHandler

# In __init__ method, after tool_router setup:
self.camera_request_handler = CameraRequestHandler(self.floor_plan, self.mqtt_client)
self.camera_request_handler.subscribe()
```

**Step 6: Run full test suite**

Run: `uv run pytest -x --tb=short`
Expected: All tests pass (125+ tests)

**Step 7: Commit**

```bash
git add houseagent/handlers/camera_request_handler.py tests/test_camera_request_handler.py houseagent/house_bot.py
git commit -m "feat: add camera request handler for dashboard integration"
```

---

## Task 2: Dashboard Backend API Endpoints

**Files:**
- Modify: `web_dashboard.py` (add MQTT publish, API routes)
- Test: `tests/test_web_dashboard.py` (create new test file)

**Step 1: Write failing test for camera capture API**

Create `tests/test_web_dashboard.py`:

```python
import json
import pytest
from unittest.mock import Mock, patch
from web_dashboard import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_camera_capture_endpoint(client):
    """Test /api/camera/capture publishes MQTT request"""
    with patch('web_dashboard.mqtt_client') as mock_mqtt:
        response = client.post('/api/camera/capture',
            json={"camera_id": "front_entrance", "zone": "entryway"})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

        # Verify MQTT publish called
        assert mock_mqtt.publish.called
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == "houseevents/camera/request"


def test_camera_refresh_all_endpoint(client):
    """Test /api/camera/refresh_all publishes requests for all cameras"""
    with patch('web_dashboard.mqtt_client') as mock_mqtt:
        with patch('web_dashboard.app') as mock_app:
            # Mock floor plan with 2 cameras
            mock_app.config = {
                'CAMERAS': [
                    {"id": "cam1", "zone": "zone1"},
                    {"id": "cam2", "zone": "zone2"}
                ]
            }

            response = client.post('/api/camera/refresh_all')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["requested"] == 2

            # Should publish 2 requests
            assert mock_mqtt.publish.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web_dashboard.py -v`
Expected: FAIL (endpoints don't exist)

**Step 3: Implement API endpoints in web_dashboard.py**

Add to `web_dashboard.py` after existing routes:

```python
# Load floor plan for camera configuration
floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
with open(floor_plan_path) as f:
    floor_plan_data = json.load(f)
    app.config['CAMERAS'] = floor_plan_data.get('cameras', [])


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
        "source": "dashboard"
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
    cameras = app.config.get('CAMERAS', [])
    count = 0

    for camera in cameras:
        request_payload = {
            "camera_id": camera["id"],
            "zone": camera.get("zone"),
            "timestamp": datetime.now().isoformat(),
            "source": "dashboard_auto"
        }
        try:
            mqtt_client.publish("houseevents/camera/request", json.dumps(request_payload))
            count += 1
        except Exception as e:
            logger.error("Failed to publish camera request", camera_id=camera["id"], error=str(e))

    return jsonify({"success": True, "requested": count})
```

Also add Flask request import at top:
```python
from flask import Flask, render_template, Response, jsonify, request
```

**Step 4: Update MQTT subscription for camera events**

Modify `on_connect` function in `web_dashboard.py`:

```python
def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to all relevant topics"""
    client.subscribe(os.getenv("SUBSCRIBE_TOPIC", "hassevents/notifications"))
    client.subscribe("office/+/+/+/+/+")
    client.subscribe(os.getenv("NOTIFICATION_TOPIC", "houseevents/ai/publish"))
    client.subscribe(os.getenv("MESSAGE_BUNDLE_TOPIC", "houseevents/ai/bundle/publish"))
    # Add camera event subscription
    client.subscribe("office/+/+/+/camera/+")
    logger.info("Dashboard subscribed to all topics including cameras")
```

**Step 5: Update message classifier for camera events**

Modify `classify_message_type` in `web_dashboard.py`:

```python
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
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_web_dashboard.py -v`
Expected: PASS (2 tests)

**Step 7: Run full test suite**

Run: `uv run pytest -x --tb=short`
Expected: All tests pass

**Step 8: Commit**

```bash
git add web_dashboard.py tests/test_web_dashboard.py
git commit -m "feat: add camera capture API endpoints to dashboard"
```

---

## Task 3: Dashboard Frontend Camera Panel

**Files:**
- Modify: `web/templates/dashboard.html` (add camera panel)
- Modify: `web/static/style.css` (add camera styles)

**Step 1: Add camera panel HTML**

Add to `web/templates/dashboard.html` after the existing 4 panels (before closing body tag):

```html
        <div class="panel">
            <div class="panel-header">
                <h2>📷 Camera Snapshots</h2>
                <button id="refresh-all-btn" class="action-btn">Refresh All</button>
            </div>
            <div id="camera-grid" class="camera-grid">
                <!-- Cameras will be populated here -->
            </div>
        </div>
    </div>

    <script>
        const cameraStates = new Map(); // Track latest snapshot per camera

        // Initialize camera grid
        function initCameraGrid() {
            const grid = document.getElementById('camera-grid');

            // Camera list will be populated from SSE events
            // Initial placeholders created on first camera event
        }

        // Update camera panel when camera event arrives
        function updateCameraSnapshot(data) {
            const cameraId = data.payload.entity_id.replace('camera.', '');
            const attrs = data.payload.attributes;

            cameraStates.set(cameraId, {
                image: attrs.image_base64,
                analysis: attrs.vision_analysis,
                zone: attrs.zone,
                name: attrs.camera_name,
                timestamp: attrs.timestamp
            });

            renderCamera(cameraId);
        }

        function renderCamera(cameraId) {
            const state = cameraStates.get(cameraId);
            if (!state) return;

            let cameraDiv = document.getElementById(`camera-${cameraId}`);
            if (!cameraDiv) {
                // Create new camera card
                const grid = document.getElementById('camera-grid');
                cameraDiv = document.createElement('div');
                cameraDiv.id = `camera-${cameraId}`;
                cameraDiv.className = 'camera-card';
                grid.appendChild(cameraDiv);
            }

            const age = Date.now() - new Date(state.timestamp).getTime();
            const ageSeconds = Math.floor(age / 1000);
            const stale = ageSeconds > 120 ? 'stale' : '';

            cameraDiv.innerHTML = `
                <div class="camera-header">
                    <span class="camera-name">${state.name}</span>
                    <span class="camera-zone">${state.zone}</span>
                </div>
                <img src="${state.image}" alt="${state.name}" class="camera-image ${stale}">
                <div class="camera-analysis">${state.analysis}</div>
                <div class="camera-footer">
                    <span class="camera-timestamp">${ageSeconds}s ago</span>
                    <button class="capture-btn" data-camera-id="${cameraId}" data-zone="${state.zone}">
                        Capture Now
                    </button>
                </div>
            `;
        }

        // Handle camera event in SSE stream
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            totalMessages++;

            if (data.type === 'camera') {
                updateCameraSnapshot(data);
            } else if (data.type === 'ai_response') {
                // existing handler
            } else if (data.type === 'situation') {
                // existing handler
            } else {
                // existing handler
            }
        };

        // Auto-refresh all cameras every 60 seconds
        setInterval(() => {
            fetch('/api/camera/refresh_all', { method: 'POST' })
                .then(r => r.json())
                .then(data => console.log('Auto-refresh:', data.requested, 'cameras'))
                .catch(err => console.error('Auto-refresh failed:', err));
        }, 60000);

        // Manual refresh all button
        document.getElementById('refresh-all-btn').addEventListener('click', () => {
            fetch('/api/camera/refresh_all', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    console.log('Manual refresh:', data.requested, 'cameras');
                    document.getElementById('refresh-all-btn').textContent = 'Refreshing...';
                    setTimeout(() => {
                        document.getElementById('refresh-all-btn').textContent = 'Refresh All';
                    }, 2000);
                });
        });

        // Per-camera capture button handler (event delegation)
        document.getElementById('camera-grid').addEventListener('click', (e) => {
            if (e.target.classList.contains('capture-btn')) {
                const cameraId = e.target.dataset.cameraId;
                const zone = e.target.dataset.zone;

                e.target.textContent = 'Capturing...';
                e.target.disabled = true;

                fetch('/api/camera/capture', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_id: cameraId, zone: zone })
                })
                .then(r => r.json())
                .then(data => {
                    console.log('Capture triggered:', cameraId);
                    setTimeout(() => {
                        e.target.textContent = 'Capture Now';
                        e.target.disabled = false;
                    }, 5000); // 5 second cooldown
                });
            }
        });

        initCameraGrid();
    </script>
</body>
```

**Step 2: Add camera panel CSS**

Add to `web/static/style.css`:

```css
/* Camera panel */
.camera-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
    padding: 0.5rem;
}

.camera-card {
    background: #0a0a0a;
    border: 2px solid #9370db;
    border-radius: 4px;
    padding: 0.5rem;
}

.camera-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #9370db;
}

.camera-name {
    color: #9370db;
    font-weight: bold;
}

.camera-zone {
    color: #666;
    font-size: 0.8em;
}

.camera-image {
    width: 100%;
    height: auto;
    border: 1px solid #333;
    margin-bottom: 0.5rem;
}

.camera-image.stale {
    opacity: 0.5;
    border-color: #ff6b6b;
}

.camera-analysis {
    color: #aaa;
    font-size: 0.9em;
    margin-bottom: 0.5rem;
    min-height: 2em;
}

.camera-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.camera-timestamp {
    color: #666;
    font-size: 0.8em;
}

.capture-btn {
    background: #9370db;
    color: #000;
    border: none;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-family: 'Courier New', monospace;
    font-size: 0.8em;
}

.capture-btn:hover {
    background: #ba8fe0;
}

.capture-btn:disabled {
    background: #555;
    cursor: not-allowed;
}

.action-btn {
    background: #9370db;
    color: #000;
    border: none;
    padding: 0.4rem 0.8rem;
    cursor: pointer;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    margin-left: 1rem;
}

.action-btn:hover {
    background: #ba8fe0;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
```

**Step 3: Manual test - restart dashboard and verify UI**

Run: `uv run web_dashboard.py`
Open: http://localhost:5001
Expected: 5th panel "Camera Snapshots" visible with purple border

**Step 4: Commit**

```bash
git add web/templates/dashboard.html web/static/style.css
git commit -m "feat: add camera snapshot panel to dashboard UI"
```

---

## Task 4: Integration Testing

**Files:**
- Create: `tests/test_camera_integration.py`

**Step 1: Write integration test**

Create `tests/test_camera_integration.py`:

```python
"""Integration test for camera dashboard feature"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock


def test_end_to_end_camera_flow():
    """Test complete flow: dashboard request → agent capture → dashboard receive"""

    # 1. Dashboard publishes request
    from web_dashboard import mqtt_client as dashboard_mqtt
    dashboard_mqtt.publish = Mock()

    request_payload = {
        "camera_id": "front_entrance",
        "zone": "entryway",
        "timestamp": "2025-10-14T12:00:00Z",
        "source": "dashboard"
    }

    dashboard_mqtt.publish("houseevents/camera/request", json.dumps(request_payload))
    assert dashboard_mqtt.publish.called

    # 2. Agent receives and processes
    from houseagent.handlers.camera_request_handler import CameraRequestHandler
    from houseagent.floor_plan import FloorPlanModel

    floor_plan = FloorPlanModel.from_file("config/floor_plan.json")
    agent_mqtt = Mock()
    handler = CameraRequestHandler(floor_plan, agent_mqtt)

    with patch('houseagent.tools.camera_tool.CameraTool.execute') as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "camera_id": "front_entrance",
            "zone": "entryway",
            "analysis": "Test analysis",
            "snapshot_path": "/tmp/test.jpg"
        }

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'test_data'

            handler.handle_request(json.dumps(request_payload))

    # 3. Verify agent published office sensor event
    assert agent_mqtt.publish.called
    topic = agent_mqtt.publish.call_args[0][0]
    assert topic == "office/default/1/entryway/camera/front_entrance"

    payload = json.loads(agent_mqtt.publish.call_args[0][1])
    assert payload["entity_id"] == "camera.front_entrance"
    assert "image_base64" in payload["attributes"]
    assert payload["attributes"]["vision_analysis"] == "Test analysis"
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_camera_integration.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `uv run pytest -x --tb=short`
Expected: All tests pass (127+ tests now)

**Step 4: Update README_DASHBOARD.md**

Add camera panel documentation:

```markdown
**Camera Snapshots** (Purple)
- Live camera feeds from all 7 office cameras
- Auto-refreshes every 60 seconds
- GPT-5 vision analysis for each snapshot
- Manual "Capture Now" per camera
- Global "Refresh All" button
- Stale indicator if snapshot > 2 minutes old
```

**Step 5: Commit**

```bash
git add tests/test_camera_integration.py README_DASHBOARD.md
git commit -m "test: add camera dashboard integration tests and docs"
```

---

## Completion Criteria

- [ ] Camera request handler subscribes to MQTT and processes requests
- [ ] Dashboard publishes camera requests on demand and auto-refresh
- [ ] Camera panel displays all 7 cameras with images and vision analysis
- [ ] Manual capture buttons trigger individual camera updates
- [ ] Auto-refresh cycles every 60 seconds
- [ ] All 127+ tests pass
- [ ] Documentation updated

## Notes

- Image size limited to ~1MB base64 (prevents MQTT message size issues)
- Camera capture is async - responses arrive over several seconds
- Stale snapshots (>2min) shown with opacity to indicate outdated data
- Existing CameraTool handles ffmpeg + GPT-5 vision analysis
- Rate limiting prevents button spam (5s cooldown per manual capture)
