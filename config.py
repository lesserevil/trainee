from dataclasses import dataclass


DEFAULT_MODEL_ID = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_NVIDIA_API_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_API_KEY_ENV = "BUILD_NVIDIA_COM_API_TOKEN"


@dataclass
class Config:
    # Model
    model_id: str = DEFAULT_MODEL_ID
    backend: str = "nvidia"          # "nvidia", "auto", "vllm", or "mlx"
    nvidia_api_base_url: str = DEFAULT_NVIDIA_API_BASE_URL
    nvidia_api_key_env: str = DEFAULT_NVIDIA_API_KEY_ENV
    nvidia_max_tokens: int = 1024
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

    # Audio (required for normal operation; --no-audio is diagnostic only)
    use_audio: bool = True
    whisper_model_size: str = "large-v3"
    audio_chunk_seconds: int = 8

    # Context / accumulation
    compress_every_n_frames: int = 10    # compress older frames after N new ones
    max_recent_frames_in_summary: int = 5
    max_recent_transcripts_in_summary: int = 3

    # Knowledge base output
    save_knowledge_base: bool = True
    knowledge_base_dir: str = "knowledge"
    knowledge_base_file: str | None = None

    # Orchestration
    max_iterations: int = 500            # safety stop
    post_quiz_wait: float = 2.0          # seconds to wait after submitting an answer
    page_settle_timeout: int = 5000      # ms to wait for networkidle after navigation
