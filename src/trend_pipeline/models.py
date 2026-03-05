from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Frame = dict[str, Any]


@dataclass(slots=True)
class VideoMetadata:
    platform: str
    video_id: str
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineConfig:
    frame_interval: int = 5
    blur_threshold: float = 120.0
    min_garment_keypoints: int = 12
    batch_size: int = 10


@dataclass(slots=True)
class FrameDecision:
    is_garment_rich: bool
    reason: str
    visible_keypoints: int


@dataclass(slots=True)
class DeadLetterItem:
    video_path: str
    stage: str
    reason: str
    metadata: VideoMetadata
