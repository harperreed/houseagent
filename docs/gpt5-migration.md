# GPT-5 Migration Guide

## Overview

HouseAgent has been upgraded to use GPT-5 models and the latest OpenAI Python SDK (v2.3.0).

## Changes Made

### 1. OpenAI SDK Upgrade

**Previous Version:** 1.52.2
**New Version:** 2.3.0 (released October 10, 2025)

```bash
uv add "openai>=2.3.0"
```

### 2. Model Configuration Updates

#### Default Models

| Purpose | Old Model | New Model |
|---------|-----------|-----------|
| Default/Legacy | gpt-3.5-turbo | gpt-5 |
| Classifier (routine events) | gpt-3.5-turbo | gpt-5-mini |
| Synthesis (high-severity) | gpt-4 | gpt-5 |

#### Environment Variables

New environment variables for fine-grained control:

```bash
# Fast model for routine events (cost-optimized)
CLASSIFIER_MODEL=gpt-5-mini

# Premium model for high-severity situations (quality-optimized)
SYNTHESIS_MODEL=gpt-5

# Legacy compatibility variable
OPENAI_MODEL=gpt-5
```

### 3. Available GPT-5 Models

HouseAgent can use any of these GPT-5 variants:

- **gpt-5** - Standard GPT-5 model (balanced performance/cost)
- **gpt-5-mini** - Smaller, faster, cheaper (ideal for routine events)
- **gpt-5-nano** - Smallest variant (ultra-low latency)
- **gpt-5-pro** - Extended reasoning capabilities (complex situations)
- **gpt-5-codex** - Optimized for code generation and agentic tasks

### 4. Code Changes

#### `houseagent/house_bot.py`

```python
# Before
openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
self.classifier_model = "gpt-3.5-turbo"
self.synthesis_model = os.getenv("OPENAI_MODEL", "gpt-4")

# After
openai_model = os.getenv("OPENAI_MODEL", "gpt-5")
self.classifier_model = os.getenv("CLASSIFIER_MODEL", "gpt-5-mini")
self.synthesis_model = os.getenv("SYNTHESIS_MODEL", "gpt-5")
```

#### Configuration Files

- Updated `.env.example` with GPT-5 model options (consolidated all phase configs)
- Updated `README.md` documentation
- Updated all tests to use GPT-5 model names

### 5. Multi-Model Strategy

HouseAgent uses severity-based model selection:

```python
severity = self._classify_severity(state)
selected_model = self.synthesis_model if severity > 0.7 else self.classifier_model
```

**Low Severity (< 0.7):** Uses `gpt-5-mini` for cost efficiency
**High Severity (>= 0.7):** Uses `gpt-5` for maximum capability

Severity factors:
- Confidence score (0.3 weight)
- Anomaly scores > 2.5 (0.4 weight)
- Multiple zones affected (0.2 weight)

### 6. GPT-5 Capabilities

GPT-5 provides significant improvements over GPT-4:

- **Context Window:** Up to 256K tokens (vs GPT-4's 128K)
- **Native Multimodal:** Text, image, audio, video input
- **Integrated Tools:** Built-in tool usage support
- **Persistent Memory:** Cross-conversation memory capabilities
- **Performance:** 74.9% on SWE-bench Verified, 88% on Aider polyglot

### 7. Breaking Changes

The OpenAI SDK v2.x has minimal breaking changes that don't affect HouseAgent:

- Tool call output types changed from `string` to `string | Array<...>`
- HouseAgent doesn't use this specific API, so no code changes needed

### 8. Testing

All 121 tests pass with GPT-5 configuration:

```bash
uv run pytest
# ============================= 121 passed in 2.31s ==============================
```

## Migration Checklist

- [x] Update OpenAI SDK to v2.3.0
- [x] Update default models to GPT-5 variants
- [x] Add CLASSIFIER_MODEL and SYNTHESIS_MODEL env vars
- [x] Update configuration examples
- [x] Update documentation
- [x] Update all tests
- [x] Verify all tests pass

## Rollback Procedure

If needed, revert to GPT-4:

```bash
# In your .env file:
CLASSIFIER_MODEL=gpt-3.5-turbo
SYNTHESIS_MODEL=gpt-4
OPENAI_MODEL=gpt-4
```

Or downgrade the SDK:

```bash
uv add "openai<2.0"
```

## Performance Considerations

### Cost Optimization

GPT-5-mini is ~70% cheaper than standard GPT-5 while maintaining excellent performance for routine events. The multi-model strategy ensures cost-efficient operation:

- Routine events (70% of situations): gpt-5-mini
- Critical events (30% of situations): gpt-5

### Latency

GPT-5-mini provides lower latency than GPT-5, making it ideal for real-time office monitoring where most events are routine.

## Future Enhancements

Consider these GPT-5 capabilities for future development:

1. **Multimodal Input:** Process camera images directly in situations
2. **Persistent Memory:** Track long-term building patterns
3. **Extended Context:** Analyze full day of events in single context
4. **GPT-5-Codex:** Auto-generate custom tools based on building needs

## References

- [OpenAI GPT-5 Documentation](https://platform.openai.com/docs/models/gpt-5)
- [OpenAI Python SDK v2.3.0 Release](https://github.com/openai/openai-python/releases)
- [GPT-5 Announcement](https://openai.com/index/introducing-gpt-5/)
