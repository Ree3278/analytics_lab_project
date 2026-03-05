# Modular Video Framing Pipeline

Python OOD scaffold for industrial video framing with:
- `TrendPipeline` orchestrator
- Swappable workers (`FrameExtractor`, `QualityAnalyst`, `AnatomyMapper`, `DataStash`)
- Platform adapters (`TikTokAdapter`, `PinterestAdapter`, `RednoteAdapter`)
- Batch decorator for multi-video processing
- Dead-letter queue for discarded videos

## Run example

```bash
uv sync
uv run python -m trend_pipeline.example
```

## Run tests

```bash
uv run pytest -q
```
