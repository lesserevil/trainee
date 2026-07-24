"""Audio transcription via faster-whisper."""

from __future__ import annotations

import numpy as np

from config import DEFAULT_WHISPER_MODEL_SIZE


class Transcriber:
    """Load a pre-downloaded faster-whisper model for transcription."""

    def __init__(self, model_size: str = DEFAULT_WHISPER_MODEL_SIZE) -> None:
        self._model_size = model_size
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model

        print(f"[transcriber] Loading cached Whisper {self._model_size}...")
        try:
            model_path = download_model(
                self._model_size,
                local_files_only=True,
            )
        except Exception as error:
            raise RuntimeError(
                f"Whisper {self._model_size} is not installed locally. "
                "Run `make setup` before starting trainee."
            ) from error
        self._model = WhisperModel(
            model_path,
            device="auto",
            compute_type="auto",
        )
        print("[transcriber] Whisper loaded.")

    def transcribe_chunk(self, audio_chunk: np.ndarray) -> str:
        """Transcribe a float32 numpy audio array sampled at 16 kHz."""
        segments, _ = self._model.transcribe(
            audio_chunk,
            beam_size=5,
            language="en",
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        if text:
            print(f"\n[audio] {text}\n")
        return text
