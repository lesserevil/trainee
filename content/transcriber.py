"""Audio transcription with automatic local backend selection."""

from __future__ import annotations

import importlib
import platform

import numpy as np

from config import DEFAULT_WHISPER_MODEL_SIZE


MLX_WHISPER_REPOSITORIES = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "distil-large-v3": "mlx-community/distil-whisper-large-v3",
}
MLX_WHISPER_FILES = (
    "config.json",
    "weights.npz",
)


def _mlx_runtime_available() -> bool:
    """Return whether a working MLX Whisper runtime is importable."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False

    try:
        importlib.import_module("mlx_whisper")
    except Exception:
        return False
    return True


class _MLXWhisperBackend:
    """Apple Silicon transcription through MLX Whisper."""

    name = "mlx"

    def __init__(self, model_size: str) -> None:
        from huggingface_hub import snapshot_download
        import mlx_whisper

        repository = MLX_WHISPER_REPOSITORIES[model_size]
        print(f"[transcriber] Loading cached MLX Whisper {model_size}...")
        try:
            model_path = snapshot_download(
                repo_id=repository,
                allow_patterns=list(MLX_WHISPER_FILES),
                local_files_only=True,
            )
        except Exception as error:
            raise RuntimeError(
                f"MLX Whisper {model_size} is not installed locally. "
                "Run `make setup` before starting trainee."
            ) from error

        self._model_path = model_path
        self._transcribe = mlx_whisper.transcribe

        # The public transcribe API owns MLX Whisper's process-wide model cache.
        # A silent warm-up eagerly loads the weights and compiles the kernels
        # before live audio capture begins.
        self._transcribe(
            np.zeros(16_000, dtype=np.float32),
            path_or_hf_repo=self._model_path,
            language="en",
            temperature=0.0,
            verbose=None,
        )
        print("[transcriber] MLX Whisper loaded and warmed.")

    def transcribe_chunk(self, audio_chunk: np.ndarray) -> str:
        result = self._transcribe(
            audio_chunk,
            path_or_hf_repo=self._model_path,
            language="en",
            temperature=0.0,
            verbose=None,
        )
        return str(result.get("text", "")).strip()


class _FasterWhisperBackend:
    """Portable transcription through faster-whisper and CTranslate2."""

    name = "faster-whisper"

    def __init__(self, model_size: str) -> None:
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model

        print(f"[transcriber] Loading cached faster-whisper {model_size}...")
        try:
            model_path = download_model(
                model_size,
                local_files_only=True,
            )
        except Exception as error:
            raise RuntimeError(
                f"faster-whisper {model_size} is not installed locally. "
                "Run `make setup` before starting trainee."
            ) from error
        self._model = WhisperModel(
            model_path,
            device="auto",
            compute_type="auto",
        )
        print("[transcriber] faster-whisper loaded.")

    def transcribe_chunk(self, audio_chunk: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio_chunk,
            beam_size=5,
            language="en",
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments)


class Transcriber:
    """Use MLX Whisper when available, otherwise use faster-whisper."""

    def __init__(self, model_size: str = DEFAULT_WHISPER_MODEL_SIZE) -> None:
        self._model_size = model_size
        if (
            self._model_size in MLX_WHISPER_REPOSITORIES
            and _mlx_runtime_available()
        ):
            self._backend = _MLXWhisperBackend(self._model_size)
        else:
            self._backend = _FasterWhisperBackend(self._model_size)

        self.backend_name = self._backend.name
        print(f"[transcriber] Using {self.backend_name} backend.")

    def transcribe_chunk(self, audio_chunk: np.ndarray) -> str:
        """Transcribe a float32 numpy audio array sampled at 16 kHz."""
        text = self._backend.transcribe_chunk(audio_chunk)
        if text:
            print(f"\n[audio] {text}\n")
        return text
