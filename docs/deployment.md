# Deployment Guide

## Prerequisites

- Docker and Docker Compose
- MQTT broker accessible from container
- OpenAI API key
- Floor plan JSON configured

## Configuration

1. Copy example config:
```bash
cp config/production.env.example .env
```

2. Edit `.env` with your settings:
   - MQTT broker address
   - OpenAI API key
   - Floor plan path
   - Camera RTSP URLs (if using camera tools)

3. Create floor plan config at `config/floor_plan.json`

## Docker Deployment

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f house-agent

# Stop services
docker-compose down
```

## Monitoring

Logs are structured JSON via structlog. Key events:

- `message.validated` - Message passed validation
- `message.filtered` - Message suppressed by noise filter
- `situation.built` - Situation created from batch
- `tool.executed` - Tool execution result
- `anomaly.detected` - Anomaly flagged

## Troubleshooting

### No messages received
- Check MQTT broker connectivity
- Verify topic subscriptions match sensor topics
- Check `SUBSCRIBE_TOPIC` and office topic pattern

### Validation errors
- Check sensor message format matches schema
- Review `message.validation_failed` logs
- Verify zone mappings in config

### Tools not executing
- Ensure `ENABLE_TOOLS=true`
- Check floor plan JSON is valid
- Review tool budget settings
