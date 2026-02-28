"""Audio transcription via faster-whisper."""

from __future__ import annotations

import numpy as np


class Transcriber:
    """Lazy-loads a faster-whisper WhisperModel on first use."""

    _model = None

    def __init__(self, model_size: str = "large-v3") -> None:
        self._model_size = model_size

    def _get_model(self):
        if Transcriber._model is None:
            from faster_whisper import WhisperModel  # lazy import

            print(f"[transcriber] Loading Whisper {self._model_size}...")
            Transcriber._model = WhisperModel(
                self._model_size,
                device="auto",
                compute_type="auto",
            )
            print("[transcriber] Whisper loaded.")
        return Transcriber._model

    def transcribe_chunk(self, audio_chunk: np.ndarray) -> str:
        """Transcribe a float32 numpy audio array sampled at 16 kHz."""
        model = self._get_model()
        segments, _ = model.transcribe(
            audio_chunk,
            beam_size=5,
            language="en",
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        if text:
            print(f"\n[audio] {text}\n")
        return text
