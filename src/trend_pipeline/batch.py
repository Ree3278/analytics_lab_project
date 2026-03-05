from __future__ import annotations

from .adapters import PlatformAdapter
from .decorators import batch_videos
from .models import PipelineConfig
from .pipeline import TrendPipeline
from .processors import AnatomyMapper, DataStash, DeadLetterQueue, FrameExtractor, QualityAnalyst


class BatchTrendRunner:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.data_stash = DataStash()
        self.dead_letter_queue = DeadLetterQueue()

    @batch_videos(batch_size=10)
    def process_batch(self, videos: list[tuple[str, dict]]) -> list[dict]:
        adapter = PlatformAdapter()
        output: list[dict] = []
        for video_path, raw_meta in videos:
            pipeline = TrendPipeline(
                video_path=video_path,
                config_settings=self.config,
                frame_extractor=FrameExtractor(),
                quality_analyst=QualityAnalyst(self.config.blur_threshold),
                anatomy_mapper=AnatomyMapper(self.config.min_garment_keypoints),
                data_stash=self.data_stash,
                dead_letter_queue=self.dead_letter_queue,
            )
            output.extend(pipeline.run(adapter.normalize(raw_meta)))
        return output
