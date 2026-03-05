from trend_pipeline.adapters import PlatformAdapter
from trend_pipeline.models import PipelineConfig
from trend_pipeline.pipeline import TrendPipeline
from trend_pipeline.processors import AnatomyMapper, DataStash, DeadLetterQueue, FrameExtractor, QualityAnalyst


def test_pipeline_emits_golden_frames() -> None:
    config = PipelineConfig(frame_interval=2, blur_threshold=100.0, min_garment_keypoints=12)
    stash = DataStash()
    dlq = DeadLetterQueue()

    pipeline = TrendPipeline(
        video_path="videos/a.mp4",
        config_settings=config,
        frame_extractor=FrameExtractor(),
        quality_analyst=QualityAnalyst(config.blur_threshold),
        anatomy_mapper=AnatomyMapper(config.min_garment_keypoints),
        data_stash=stash,
        dead_letter_queue=dlq,
    )

    metadata = PlatformAdapter().normalize({"video_id": "v-1", "platform": "generic"})
    results = pipeline.run(metadata)

    assert results
    assert not dlq.items


def test_pipeline_dead_letters_when_strict_thresholds() -> None:
    config = PipelineConfig(frame_interval=3, blur_threshold=9999.0, min_garment_keypoints=99)
    stash = DataStash()
    dlq = DeadLetterQueue()

    pipeline = TrendPipeline(
        video_path="videos/b.mp4",
        config_settings=config,
        frame_extractor=FrameExtractor(),
        quality_analyst=QualityAnalyst(config.blur_threshold),
        anatomy_mapper=AnatomyMapper(config.min_garment_keypoints),
        data_stash=stash,
        dead_letter_queue=dlq,
    )

    metadata = PlatformAdapter().normalize({"video_id": "v-2", "platform": "generic"})
    results = pipeline.run(metadata)

    assert not results
    assert len(dlq.items) == 1
