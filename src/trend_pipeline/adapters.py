from __future__ import annotations

from dataclasses import asdict

from .base import PlatformAdapterInterface
from .models import VideoMetadata


class PlatformAdapter(PlatformAdapterInterface):
    platform_name = "generic"

    def normalize(self, payload: dict) -> dict:
        return {
            "platform": payload.get("platform", self.platform_name),
            "video_id": str(payload.get("video_id", "unknown")),
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "tags": payload.get("tags", []),
            "extra": payload.get("extra", {}),
        }


class TikTokAdapter(PlatformAdapter):
    platform_name = "tiktok"

    def normalize(self, payload: dict) -> dict:
        return asdict(
            VideoMetadata(
            platform=self.platform_name,
            video_id=str(payload.get("aweme_id", payload.get("video_id", "unknown"))),
            title=payload.get("title", ""),
            description=payload.get("desc", payload.get("description", "")),
            tags=payload.get("hashtags", payload.get("tags", [])),
            extra={"author_id": payload.get("author_id")},
            )
        )


class PinterestAdapter(PlatformAdapter):
    platform_name = "pinterest"

    def normalize(self, payload: dict) -> dict:
        return asdict(
            VideoMetadata(
            platform=self.platform_name,
            video_id=str(payload.get("pin_id", payload.get("video_id", "unknown"))),
            title=payload.get("title", ""),
            description=payload.get("description", ""),
            tags=payload.get("board_tags", payload.get("tags", [])),
            extra={"board": payload.get("board_name")},
            )
        )


class RednoteAdapter(PlatformAdapter):
    platform_name = "rednote"

    def normalize(self, payload: dict) -> dict:
        return asdict(
            VideoMetadata(
            platform=self.platform_name,
            video_id=str(payload.get("note_id", payload.get("video_id", "unknown"))),
            title=payload.get("title", ""),
            description=payload.get("content", payload.get("description", "")),
            tags=payload.get("topic_tags", payload.get("tags", [])),
            extra={"user": payload.get("user_id")},
            )
        )
