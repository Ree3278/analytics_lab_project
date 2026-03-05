from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .models import Frame, FrameDecision


class Processor(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


class FrameExtractorInterface(Processor):
    @abstractmethod
    def extract_frames(self, video_path: str, interval: int) -> list[Frame]:
        raise NotImplementedError


class QualityAnalystInterface(Processor):
    @abstractmethod
    def is_high_quality(self, frame: Frame) -> bool:
        raise NotImplementedError


class AnatomyMapperInterface(Processor):
    @abstractmethod
    def detect_garment_visibility(self, frame: Frame) -> FrameDecision:
        raise NotImplementedError


class DataStashInterface(Processor):
    @abstractmethod
    def upload_to_storage(self, frame: Frame, meta: dict) -> str:
        raise NotImplementedError


class DeadLetterInterface(Processor):
    @abstractmethod
    def record(self, video_path: str, stage: str, reason: str, metadata: dict) -> None:
        raise NotImplementedError


class PlatformAdapterInterface(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, payload: dict) -> dict:
        raise NotImplementedError


class BatchProcessorInterface(ABC):
    @abstractmethod
    def process_batch(self, videos: Iterable[tuple[str, dict]]) -> list[dict]:
        raise NotImplementedError
