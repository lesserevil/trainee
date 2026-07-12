"""System audio capture via BlackHole virtual audio device.

Requires:
    brew install blackhole-2ch
    Configure a Multi-Output Device in macOS Audio MIDI Setup that routes
    to both your speakers and BlackHole 2ch.

Usage:
    capture = AudioCapture()
    capture.start()
    ...
    chunk = capture.get_chunk()   # returns np.ndarray or None
    capture.stop()
"""

from __future__ import annotations

import queue
import sys
import threading

import numpy as np

BLACKHOLE_DEVICE_NAME = "BlackHole 2ch"
MULTI_OUTPUT_SUBSTRING = "Multi-Output"


def check_audio_setup() -> None:
    """
    Verify the audio capture prerequisites are in place.
    Exits with a clear message if anything is missing.
    """
    try:
        import sounddevice as sd
    except ImportError:
        print(
            "ERROR: The 'sounddevice' package is not installed.\n"
            "       Re-install dependencies with the audio extra:\n"
            "       uv pip install -e '.[mlx,audio]'    # Apple Silicon\n"
            "       uv pip install -e '.[vllm,audio]'   # NVIDIA CUDA"
        )
        sys.exit(1)

    devices = sd.query_devices()
    names = [d["name"] for d in devices]

    has_blackhole = any(BLACKHOLE_DEVICE_NAME in n for n in names)
    has_multi_output = any(MULTI_OUTPUT_SUBSTRING in n for n in names)

    if not has_blackhole or not has_multi_output:
        print()
        print("=" * 60)
        print("  Audio setup is incomplete.")
        print()
        if not has_blackhole:
            print("  MISSING: BlackHole 2ch audio driver")
            print("    BlackHole is a virtual audio device that lets trainee")
            print("    listen to the course audio while it plays normally")
            print("    through your speakers.")
        if not has_multi_output:
            print("  MISSING: Multi-Output Device")
            print("    A Multi-Output Device routes audio to both your")
            print("    speakers and BlackHole so trainee can capture it.")
        print()
        print("  Audio capture is required for normal operation.")
        print("  Complete the setup in README.md:")
        print()
        print("      brew install blackhole-2ch")
        print("      # then create and select a Multi-Output Device")
        print()
        print("  For a visual-only diagnostic run:")
        print()
        print("      python trainee.py --url '...' --no-audio")
        print("=" * 60)
        print()
        sys.exit(1)


SAMPLE_RATE = 16_000   # Hz — matches Whisper's expected input rate
CHANNELS = 1


class AudioCapture:
    def __init__(self, chunk_seconds: int = 30) -> None:
        import sounddevice as sd  # import here so absence of sounddevice is not fatal at import time

        self._sd = sd
        self._chunk_seconds = chunk_seconds
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._buffer: list[float] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._device_index = self._find_blackhole()

    def _find_blackhole(self) -> int:
        devices = self._sd.query_devices()
        for i, d in enumerate(devices):
            if BLACKHOLE_DEVICE_NAME in d["name"]:
                return i
        raise RuntimeError(
            f"BlackHole device '{BLACKHOLE_DEVICE_NAME}' not found.\n"
            "Install with: brew install blackhole-2ch\n"
            "Then create a Multi-Output Device in macOS Audio MIDI Setup "
            "that includes both your speakers and BlackHole 2ch."
        )

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        print("[audio] Started capturing from BlackHole")

    def _record_loop(self) -> None:
        with self._sd.InputStream(
            device=self._device_index,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            callback=self._audio_callback,
        ):
            stop_event = threading.Event()
            while self._running:
                stop_event.wait(timeout=0.1)

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        self._buffer.extend(indata[:, 0].tolist())
        chunk_size = SAMPLE_RATE * self._chunk_seconds
        if len(self._buffer) >= chunk_size:
            chunk = np.array(self._buffer[:chunk_size], dtype=np.float32)
            self._queue.put(chunk)
            self._buffer = self._buffer[chunk_size:]

    def get_chunk(self) -> np.ndarray | None:
        """Return the next ready audio chunk, or None if none available."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        print("[audio] Stopped")
