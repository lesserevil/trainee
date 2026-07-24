"""Native macOS system-audio capture.

The bundled Swift helper uses a private Core Audio process tap and streams
16 kHz mono float32 PCM to this module. Normal speaker or headphone routing is
left unchanged.
"""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
CHANNELS = 1
STREAM_MAGIC = b"TRNEAUD1"
MINIMUM_MACOS_VERSION = (14, 2)
START_TIMEOUT_SECONDS = 15.0
HELPER_ENV_VAR = "TRAINEE_AUDIO_CAPTURE_HELPER"
DEFAULT_HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / ".build"
    / "trainee-audio-capture.app"
    / "Contents"
    / "MacOS"
    / "trainee-audio-capture"
)


def _macos_version_tuple(version: str) -> tuple[int, int]:
    try:
        parts = [int(part) for part in version.split(".")[:2]]
    except ValueError:
        return (0, 0)
    return tuple((parts + [0, 0])[:2])


def audio_helper_path() -> Path:
    override = os.environ.get(HELPER_ENV_VAR)
    return Path(override).expanduser() if override else DEFAULT_HELPER_PATH


def check_audio_setup() -> None:
    """Exit with a useful message when native system capture is unavailable."""
    problems: list[str] = []

    if sys.platform != "darwin":
        problems.append("native system audio capture requires macOS")
    else:
        current_version = _macos_version_tuple(platform.mac_ver()[0])
        if current_version < MINIMUM_MACOS_VERSION:
            problems.append(
                "native system audio capture requires macOS 14.2 or newer "
                f"(this Mac is running {platform.mac_ver()[0] or 'an unknown version'})"
            )

    helper = audio_helper_path()
    if not helper.is_file() or not os.access(helper, os.X_OK):
        problems.append(
            f"the native audio helper is missing at {helper}\n"
            "    Build it with: make build"
        )

    if not problems:
        return

    print()
    print("=" * 60)
    print("  Audio capture is unavailable.")
    print()
    for problem in problems:
        print(f"  - {problem}")
    print()
    print("  Run `make setup`, then try again.")
    print("  Use --no-audio only for a visual-only diagnostic run.")
    print("=" * 60)
    print()
    raise SystemExit(1)


class AudioCapture:
    """Capture the global macOS audio mix in Whisper-ready chunks."""

    def __init__(
        self,
        chunk_seconds: int = 30,
        *,
        helper_path: Path | None = None,
        popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    ) -> None:
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be positive")

        self._chunk_seconds = chunk_seconds
        self._helper_path = helper_path or audio_helper_path()
        self._popen_factory = popen_factory
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._byte_buffer = bytearray()
        self._bytes_per_chunk = (
            SAMPLE_RATE * CHANNELS * chunk_seconds * np.dtype("<f4").itemsize
        )
        self._process: subprocess.Popen[bytes] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._running = False
        self._started = False
        self._error_lock = threading.Lock()
        self._reader_error: RuntimeError | None = None
        self._stderr_lines: list[str] = []

    def start(self) -> None:
        if self._running:
            return
        if not self._helper_path.is_file() or not os.access(
            self._helper_path, os.X_OK
        ):
            raise RuntimeError(
                f"Native audio helper not found at {self._helper_path}. "
                "Run `make build` first."
            )

        self._running = True
        self._started = False
        self._ready.clear()
        self._byte_buffer.clear()
        self._reader_error = None
        self._stderr_lines.clear()
        try:
            self._process = self._popen_factory(
                [str(self._helper_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as error:
            self._running = False
            raise RuntimeError(
                f"Could not launch the native audio helper: {error}"
            ) from error

        self._reader_thread = threading.Thread(
            target=self._read_audio,
            name="trainee-audio-reader",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="trainee-audio-stderr",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread.start()

        if not self._ready.wait(timeout=START_TIMEOUT_SECONDS):
            details = self._stderr_summary()
            self.stop()
            raise RuntimeError(
                "Timed out while starting native system audio capture."
                f"{details}\n"
                "Check System Settings > Privacy & Security and allow "
                "trainee Audio Capture to record system audio."
            )

        error = self._get_reader_error()
        if error is not None:
            self.stop()
            raise error

        self._started = True
        print("[audio] Started native macOS system audio capture")

    def _read_audio(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            self._set_reader_error("The native audio helper has no output stream")
            return

        try:
            header = self._read_exact(process.stdout, len(STREAM_MAGIC))
            if header != STREAM_MAGIC:
                self._set_reader_error(
                    "The native audio helper returned an invalid stream header"
                )
                return
            self._ready.set()

            while self._running:
                data = process.stdout.read(64 * 1024)
                if not data:
                    break
                self._byte_buffer.extend(data)
                self._emit_complete_chunks()

            if self._running:
                return_code = process.poll()
                details = self._stderr_summary()
                message = "Native system audio capture stopped unexpectedly"
                if return_code is not None:
                    message += f" with exit code {return_code}"
                self._set_reader_error(f"{message}.{details}")
        except OSError as error:
            if self._running:
                self._set_reader_error(
                    f"Could not read native system audio: {error}"
                )

    @staticmethod
    def _read_exact(stream, size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            data = stream.read(size - len(result))
            if not data:
                break
            result.extend(data)
        return bytes(result)

    def _emit_complete_chunks(self) -> None:
        while len(self._byte_buffer) >= self._bytes_per_chunk:
            payload = bytes(self._byte_buffer[: self._bytes_per_chunk])
            del self._byte_buffer[: self._bytes_per_chunk]
            chunk = np.frombuffer(payload, dtype="<f4").astype(np.float32, copy=True)
            self._queue.put(chunk)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for raw_line in iter(process.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            with self._error_lock:
                self._stderr_lines.append(line)
                del self._stderr_lines[:-10]
            print(line, file=sys.stderr)

    def _stderr_summary(self) -> str:
        with self._error_lock:
            if not self._stderr_lines:
                return ""
            return "\n" + "\n".join(self._stderr_lines)

    def _set_reader_error(self, message: str) -> None:
        with self._error_lock:
            if self._reader_error is None:
                self._reader_error = RuntimeError(message)
        self._ready.set()

    def _get_reader_error(self) -> RuntimeError | None:
        with self._error_lock:
            return self._reader_error

    def get_chunk(self) -> np.ndarray | None:
        """Return the next ready audio chunk, or None if none is available."""
        error = self._get_reader_error()
        if error is not None:
            raise error
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        was_started = self._started
        self._running = False
        self._started = False
        process = self._process

        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2.0)

        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        self._process = None
        if was_started:
            print("[audio] Stopped")
