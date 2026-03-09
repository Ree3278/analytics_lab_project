from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
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
    def __init__(
        self,
        fps_target: float = 1.0,
        prefer_iframes: bool = True,
        ffprobe_timeout_seconds: int = 20,
    ) -> None:
        self.fps_target = fps_target
        self.prefer_iframes = prefer_iframes
        self.ffprobe_timeout_seconds = ffprobe_timeout_seconds

    @property
    def name(self) -> str:
        return "frame_extractor"

    def _probe_iframe_numbers(self, video_path: str) -> set[int]:
        if not self.prefer_iframes or not shutil.which("ffprobe"):
            return set()

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=key_frame,coded_picture_number",
            "-of",
            "json",
            video_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.ffprobe_timeout_seconds,
            )
        except (subprocess.SubprocessError, OSError):
            return set()

        try:
            payload = json.loads(result.stdout)
            frames = payload.get("frames", [])
        except json.JSONDecodeError:
            return set()

        i_frames: set[int] = set()
        for frame in frames:
            if int(frame.get("key_frame", 0)) != 1:
                continue
            frame_number = frame.get("coded_picture_number")
            if frame_number is None:
                continue
            i_frames.add(int(frame_number))
        return i_frames

    def extract_frames(self, video_path: str, interval: int) -> list[Frame]:
        video_file = Path(video_path)
        if not video_file.exists():
            return []

        try:
            import cv2  # type: ignore[import-untyped]
        except ImportError:
            return []

        capture = cv2.VideoCapture(str(video_file))
        if not capture.isOpened():
            return []

        native_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if native_fps <= 0.0:
            native_fps = 30.0

        interval = max(interval, 1)
        sample_every_n_frames = int(round(native_fps * interval))
        sample_every_n_frames = max(sample_every_n_frames, 1)

        if self.fps_target > 0:
            cap_every_n_frames = max(int(round(native_fps / self.fps_target)), 1)
            sample_every_n_frames = max(sample_every_n_frames, cap_every_n_frames)

        iframe_numbers = self._probe_iframe_numbers(str(video_file))
        frames: list[Frame] = []
        frame_index = 0

        try:
            while True:
                ok, image = capture.read()
                if not ok:
                    break

                should_sample = frame_index % sample_every_n_frames == 0
                if iframe_numbers:
                    should_sample = should_sample and frame_index in iframe_numbers

                if should_sample:
                    frames.append(
                        {
                            "id": frame_index,
                            "source": str(video_file),
                            "timestamp_sec": frame_index / native_fps,
                            "image": image,
                            "width": int(image.shape[1]),
                            "height": int(image.shape[0]),
                        }
                    )

                frame_index += 1
        finally:
            capture.release()

        return frames


class QualityAnalyst(QualityAnalystInterface):
    def __init__(self, blur_threshold: float = 120.0) -> None:
        self.blur_threshold = blur_threshold

    @property
    def name(self) -> str:
        return "quality_analyst"

    def is_high_quality(self, frame: Frame) -> bool:
        if "sharpness" in frame:
            return float(frame.get("sharpness", 0.0)) >= self.blur_threshold

        image = frame.get("image")
        if image is None:
            return False

        try:
            import cv2  # type: ignore[import-untyped]
        except ImportError:
            return False

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        frame["sharpness"] = score
        return score >= self.blur_threshold


class AnatomyMapper(AnatomyMapperInterface):
    def __init__(
        self,
        min_garment_keypoints: int = 12,
        backend: str = "auto",
        mediapipe_visibility_threshold: float = 0.5,
        yolo_model: str = "yolo11n-pose.pt",
        yolo_confidence_threshold: float = 0.35,
        yolo_device: str | None = None,
    ) -> None:
        self.min_garment_keypoints = min_garment_keypoints
        self.backend = backend
        self.mediapipe_visibility_threshold = mediapipe_visibility_threshold
        self.yolo_model = yolo_model
        self.yolo_confidence_threshold = yolo_confidence_threshold
        self.yolo_device = yolo_device

        self._active_backend = "none"
        self._mediapipe_pose: Any | None = None
        self._yolo_model: Any | None = None
        self._initialize_backend()

    @property
    def name(self) -> str:
        return "anatomy_mapper"

    def _initialize_backend(self) -> None:
        if self.backend in {"auto", "mediapipe"}:
            try:
                import mediapipe as mp  # type: ignore[import-not-found]

                self._mediapipe_pose = mp.solutions.pose.Pose(
                    static_image_mode=True,
                    model_complexity=1,
                    min_detection_confidence=0.5,
                )
                self._active_backend = "mediapipe"
                return
            except Exception:
                if self.backend == "mediapipe":
                    self._active_backend = "none"
                    return

        if self.backend in {"auto", "yolo"}:
            try:
                from ultralytics import YOLO  # type: ignore[import-not-found]

                self._yolo_model = YOLO(self.yolo_model)
                self._active_backend = "yolo"
                return
            except Exception:
                if self.backend == "yolo":
                    self._active_backend = "none"
                    return

        self._active_backend = "none"

    def _decision_from_visible_points(
        self,
        visible_points: int,
        has_shoulders: bool,
        has_torso: bool,
        has_legs: bool,
    ) -> FrameDecision:
        if visible_points >= self.min_garment_keypoints and has_torso and has_legs:
            return FrameDecision(True, "garment_rich", visible_points)
        if has_shoulders and not (has_torso and has_legs):
            return FrameDecision(False, "accessory_or_makeup_only", visible_points)
        if visible_points > 0:
            return FrameDecision(False, "partial_body_only", visible_points)
        return FrameDecision(False, "no_valid_pose", 0)

    def _detect_with_mediapipe(self, image: Any) -> FrameDecision:
        import cv2  # type: ignore[import-untyped]

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result = self._mediapipe_pose.process(rgb)
        if not result.pose_landmarks:
            return FrameDecision(False, "no_valid_pose", 0)

        landmarks = result.pose_landmarks.landmark
        vis = [lm.visibility >= self.mediapipe_visibility_threshold for lm in landmarks]
        visible_points = sum(1 for ok in vis if ok)

        has_shoulders = vis[11] or vis[12]
        has_torso = vis[11] and vis[12] and (vis[23] or vis[24])
        has_legs = (vis[25] or vis[26]) and (vis[27] or vis[28])

        return self._decision_from_visible_points(
            visible_points=visible_points,
            has_shoulders=has_shoulders,
            has_torso=has_torso,
            has_legs=has_legs,
        )

    def _detect_with_yolo(self, image: Any) -> FrameDecision:
        predictions = self._yolo_model.predict(  # type: ignore[union-attr]
            image,
            verbose=False,
            conf=self.yolo_confidence_threshold,
            device=self.yolo_device,
        )
        if not predictions:
            return FrameDecision(False, "no_valid_pose", 0)

        keypoints = predictions[0].keypoints
        if keypoints is None or keypoints.data is None or len(keypoints.data) == 0:
            return FrameDecision(False, "no_valid_pose", 0)

        person = keypoints.data[0].cpu().numpy()
        if person.shape[1] < 3:
            return FrameDecision(False, "no_valid_pose", 0)

        conf = person[:, 2]
        visible = conf >= self.yolo_confidence_threshold
        visible_points = int(visible.sum())

        has_shoulders = bool(visible[5] or visible[6])
        has_torso = bool((visible[5] or visible[6]) and (visible[11] or visible[12]))
        has_legs = bool((visible[13] or visible[14]) and (visible[15] or visible[16]))

        return self._decision_from_visible_points(
            visible_points=visible_points,
            has_shoulders=has_shoulders,
            has_torso=has_torso,
            has_legs=has_legs,
        )

    def detect_garment_visibility(self, frame: Frame) -> FrameDecision:
        # Backward-compatible path for precomputed keypoint counts used in tests/mocks.
        if "keypoints" in frame and "image" not in frame:
            keypoints = int(frame.get("keypoints", 0))
            return self._decision_from_visible_points(
                visible_points=keypoints,
                has_shoulders=keypoints >= 4,
                has_torso=keypoints >= 8,
                has_legs=keypoints >= 10,
            )

        image = frame.get("image")
        if image is None:
            return FrameDecision(False, "no_image_in_frame", 0)

        if self._active_backend == "mediapipe":
            return self._detect_with_mediapipe(image)
        if self._active_backend == "yolo":
            return self._detect_with_yolo(image)

        return FrameDecision(False, "pose_backend_unavailable", 0)


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
