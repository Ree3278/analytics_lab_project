# Modular Video Framing Pipeline

Python OOD scaffold for industrial video framing with:
- `TrendPipeline` orchestrator
- Swappable workers (`FrameExtractor`, `QualityAnalyst`, `AnatomyMapper`, `DataStash`)
- Platform adapters (`TikTokAdapter`, `PinterestAdapter`, `RednoteAdapter`)
- Batch decorator for multi-video processing
- Dead-letter queue for discarded videos

## Enable vision backends

```bash
uv sync --group vision
```

Notes:
- `FrameExtractor` uses OpenCV for decode and `ffprobe` (if installed) to prefer I-frames.
- `AnatomyMapper` supports `backend=\"mediapipe\"`, `backend=\"yolo\"`, or `backend=\"auto\"`.
- MediaPipe is only installed automatically for Python `<3.13` in this project config.

## Run example

```bash
uv sync
uv run python -m trend_pipeline.example
```

## Run tests

```bash
uv run pytest -q
```
