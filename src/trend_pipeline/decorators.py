from __future__ import annotations

from collections.abc import Callable
from typing import Any


def batch_videos(batch_size: int) -> Callable:
    def decorator(func: Callable[[Any, list[tuple[str, dict]]], list[dict]]) -> Callable:
        def wrapper(self: Any, videos: list[tuple[str, dict]]) -> list[dict]:
            all_results: list[dict] = []
            for i in range(0, len(videos), max(batch_size, 1)):
                chunk = videos[i : i + batch_size]
                all_results.extend(func(self, chunk))
            return all_results

        return wrapper

    return decorator
