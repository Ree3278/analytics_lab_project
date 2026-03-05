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
from .models import PipelineConfig, VideoMetadata


class TrendPipeline:
    def __init__(
        self,
        video_path: str,
        config_settings: PipelineConfig,
        frame_extractor: FrameExtractorInterface,
        quality_analyst: QualityAnalystInterface,
        anatomy_mapper: AnatomyMapperInterface,
        data_stash: DataStashInterface,
        dead_letter_queue: DeadLetterInterface,
    ) -> None:
        self.video_path = video_path
        self.config_settings = config_settings
        self.frame_extractor = frame_extractor
        self.quality_analyst = quality_analyst
        self.anatomy_mapper = anatomy_mapper
        self.data_stash = data_stash
        self.dead_letter_queue = dead_letter_queue
        self.results_buffer: list[dict[str, Any]] = []

    def log_status(self, message: str) -> None:
        print(f"[TrendPipeline] {message}")

    def export_metadata(self) -> list[dict[str, Any]]:
        return list(self.results_buffer)

    def run(self, metadata: dict) -> list[dict[str, Any]]:
        normalized = VideoMetadata(**metadata)
        self.log_status(f"start video={self.video_path} id={normalized.video_id}")

        frames = self.frame_extractor.extract_frames(
            self.video_path, interval=self.config_settings.frame_interval
        )
        if not frames:
            self.dead_letter_queue.record(
                self.video_path,
                stage="extract_frames",
                reason="no_frames",
                metadata=asdict(normalized),
            )
            return []

        for frame in frames:
            if not self.quality_analyst.is_high_quality(frame):
                continue
            decision = self.anatomy_mapper.detect_garment_visibility(frame)
            if not decision.is_garment_rich:
                continue

            record_id = self.data_stash.upload_to_storage(
                frame,
                {
                    "video": asdict(normalized),
                    "decision": asdict(decision),
                },
            )
            self.results_buffer.append(
                {
                    "record_id": record_id,
                    "video_id": normalized.video_id,
                    "frame_id": frame.get("id"),
                    "keypoints": decision.visible_keypoints,
                }
            )

        if not self.results_buffer:
            self.dead_letter_queue.record(
                self.video_path,
                stage="quality_or_pose",
                reason="no_golden_frames",
                metadata=asdict(normalized),
            )

        self.log_status(
            f"complete video={self.video_path} golden_frames={len(self.results_buffer)}"
        )
        return self.export_metadata()
