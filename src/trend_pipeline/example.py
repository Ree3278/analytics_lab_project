from trend_pipeline.adapters import TikTokAdapter
from trend_pipeline.models import PipelineConfig
from trend_pipeline.pipeline import TrendPipeline
from trend_pipeline.processors import AnatomyMapper, DataStash, DeadLetterQueue, FrameExtractor, QualityAnalyst


if __name__ == "__main__":
    config = PipelineConfig(frame_interval=3, blur_threshold=110.0, min_garment_keypoints=12)
    adapter = TikTokAdapter()
    stash = DataStash()
    dlq = DeadLetterQueue()

    pipeline = TrendPipeline(
        video_path="videos/sample_tiktok.mp4",
        config_settings=config,
        frame_extractor=FrameExtractor(fps_target=1.5),
        quality_analyst=QualityAnalyst(blur_threshold=config.blur_threshold),
        anatomy_mapper=AnatomyMapper(
            min_garment_keypoints=config.min_garment_keypoints,
            backend="auto",
        ),
        data_stash=stash,
        dead_letter_queue=dlq,
    )

    raw_meta = {
        "aweme_id": "1234567",
        "title": "streetwear drop",
        "desc": "spring fit check",
        "hashtags": ["streetwear", "ootd"],
        "author_id": "creator_88",
    }

    results = pipeline.run(adapter.normalize(raw_meta))
    print("Golden frames:", results)
    print("Dead letter:", dlq.dump())
