# HouseAgent Web Dashboard

Real-time monitoring interface for HouseAgent with live MQTT message streaming.

## Features

- **Real-time Updates**: Server-Sent Events (SSE) for instant message streaming
- **GlaDOS Responses**: See AI-generated responses as they happen
- **Situation Detection**: Monitor clustered events and correlated sensor data
- **Sensor Events**: Live feed of all sensor activity
- **System Log**: Complete event history

## Running the Dashboard

### Local Development

```bash
uv run web_dashboard.py
```

Access at: http://localhost:5001

### Docker Compose

```bash
docker-compose up dashboard
```

Access at: http://localhost:5001

## Dashboard Panels

**GlaDOS Responses** (Magenta)
- AI-generated witty responses
- Updates when agent publishes to NOTIFICATION_TOPIC

**Situations Detected** (Cyan)
- Clustered sensor events
- Shows zones, sensor types, and confidence scores
- Updates from MESSAGE_BUNDLE_TOPIC

**Recent Sensor Events** (Yellow)
- Individual sensor messages
- Home Assistant entity updates
- Office hierarchical sensor data

**All Events** (Green)
- Complete system log
- Raw MQTT message payloads
- Debugging and monitoring

**Camera Snapshots** (Purple)
- Camera feeds from all 7 office cameras
- Manual refresh only (use "Refresh All" button)
- GPT-5 vision analysis for each snapshot
- Per-camera "Capture Now" button
- Global "Refresh All" button
- Stale indicator if snapshot > 2 minutes old
- **Note:** Auto-refresh disabled to avoid excessive API costs

## Configuration

The dashboard automatically uses your `.env` configuration:
- `MQTT_BROKER_ADDRESS` - MQTT broker host
- `MQTT_PORT` - MQTT broker port
- `MQTT_USERNAME` / `MQTT_PASSWORD` - Authentication (optional)
- `SUBSCRIBE_TOPIC` - Legacy sensor topic
- `NOTIFICATION_TOPIC` - AI response topic
- `MESSAGE_BUNDLE_TOPIC` - Situation bundles topic
- `FLOOR_PLAN_PATH` - Floor plan JSON for camera configuration

**MQTT Client ID:** Each dashboard instance uses a unique UUID-based client ID (`dashboard-{8-char-hex}`) to prevent broker connection conflicts when running multiple instances.

## Theme

Classic terminal aesthetic with color-coded message types:
- 🟣 Magenta = AI Responses (GlaDOS)
- 🔵 Cyan = Situations (Event clusters)
- 🟡 Yellow = Sensors (Raw data)
- 🟢 Green = System messages

Matrix-style green-on-black with retro CRT vibes.
