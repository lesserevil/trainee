from dataclasses import dataclass, field


@dataclass
class Config:
    # Model
    model_id: str = "Qwen/Qwen2-VL-7B-Instruct"
    backend: str = "auto"            # "auto", "vllm", or "mlx"
    max_model_len: int = 32768       # vllm only
    max_vllm_images_per_prompt: int = 8  # vllm only

    # Browser
    headless: bool = False
    browser_viewport_width: int = 1280
    browser_viewport_height: int = 800
    browser_profile_dir: str = ".browser-profile"  # persists cookies/SSO across runs

    # Content capture
    screenshot_interval: float = 3.0     # seconds between frame captures
    screenshot_quality: int = 75         # JPEG quality 1-100

    # Audio (on by default, disable with --no-audio)
    use_audio: bool = True
    whisper_model_size: str = "large-v3"
    audio_chunk_seconds: int = 8

    # Context / accumulation
    compress_every_n_frames: int = 10    # compress older frames after N new ones
    max_recent_frames_in_summary: int = 5
    max_recent_transcripts_in_summary: int = 3

    # Orchestration
    max_iterations: int = 500            # safety stop
    post_quiz_wait: float = 2.0          # seconds to wait after submitting an answer
    page_settle_timeout: int = 5000      # ms to wait for networkidle after navigation
