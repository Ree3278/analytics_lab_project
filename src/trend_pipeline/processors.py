from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .base import (
    AnatomyMapperInterface,
    DataStashInterface,
    DeadLetterInterface,
    FrameExtractorInterface,
    QualityAnalystInterface,
)
from .models import DeadLetterItem, Frame, FrameDecision, VideoMetadata


class FrameExtractor(FrameExtractorInterface):
    def __init__(self, fps_target: float = 1.0) -> None:
        self.fps_target = fps_target

    @property
    def name(self) -> str:
        return "frame_extractor"

    def extract_frames(self, video_path: str, interval: int) -> list[Frame]:
        # Replace this mocked extraction with FFmpeg/OpenCV integration.
        return [
            {"id": i, "source": video_path, "sharpness": 70 + i * 10, "keypoints": 6 + i * 3}
            for i in range(0, 30, max(interval, 1))
        ]


class QualityAnalyst(QualityAnalystInterface):
    def __init__(self, blur_threshold: float = 120.0) -> None:
        self.blur_threshold = blur_threshold

    @property
    def name(self) -> str:
        return "quality_analyst"

    def is_high_quality(self, frame: Frame) -> bool:
        sharpness = float(frame.get("sharpness", 0.0))
        return sharpness >= self.blur_threshold


class AnatomyMapper(AnatomyMapperInterface):
    def __init__(self, min_garment_keypoints: int = 12) -> None:
        self.min_garment_keypoints = min_garment_keypoints

    @property
    def name(self) -> str:
        return "anatomy_mapper"

    def detect_garment_visibility(self, frame: Frame) -> FrameDecision:
        keypoints = int(frame.get("keypoints", 0))
        if keypoints >= self.min_garment_keypoints:
            return FrameDecision(
                is_garment_rich=True,
                reason="garment_rich",
                visible_keypoints=keypoints,
            )
        if keypoints >= 4:
            return FrameDecision(
                is_garment_rich=False,
                reason="accessory_or_makeup_only",
                visible_keypoints=keypoints,
            )
        return FrameDecision(
            is_garment_rich=False,
            reason="no_valid_pose",
            visible_keypoints=keypoints,
        )


class DataStash(DataStashInterface):
    def __init__(self) -> None:
        self.storage: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "data_stash"

    def upload_to_storage(self, frame: Frame, meta: dict) -> str:
        record_id = f"golden_{len(self.storage) + 1}"
        self.storage.append({"record_id": record_id, "frame": frame, "meta": meta})
        return record_id


class DeadLetterQueue(DeadLetterInterface):
    def __init__(self) -> None:
        self.items: list[DeadLetterItem] = []

    @property
    def name(self) -> str:
        return "dead_letter_queue"

    def record(self, video_path: str, stage: str, reason: str, metadata: dict) -> None:
        normalized = VideoMetadata(**metadata)
        self.items.append(
            DeadLetterItem(
                video_path=video_path,
                stage=stage,
                reason=reason,
                metadata=normalized,
            )
        )

    def dump(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.items]
