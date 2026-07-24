import contextlib
import io
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from content.audio_capture import (
    HELPER_ENV_VAR,
    AudioCapture,
    check_audio_setup,
)


class AudioSetupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.helper = Path(self.temp_dir.name) / "audio-helper"
        self.helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.helper.chmod(self.helper.stat().st_mode | stat.S_IXUSR)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_accepts_supported_macos_with_built_helper(self) -> None:
        with (
            mock.patch("content.audio_capture.sys.platform", "darwin"),
            mock.patch(
                "content.audio_capture.platform.mac_ver",
                return_value=("14.2.1", ("", "", ""), ""),
            ),
            mock.patch.dict(
                os.environ,
                {HELPER_ENV_VAR: str(self.helper)},
                clear=False,
            ),
        ):
            check_audio_setup()

    def test_rejects_older_macos(self) -> None:
        with (
            mock.patch("content.audio_capture.sys.platform", "darwin"),
            mock.patch(
                "content.audio_capture.platform.mac_ver",
                return_value=("13.6.9", ("", "", ""), ""),
            ),
            mock.patch.dict(
                os.environ,
                {HELPER_ENV_VAR: str(self.helper)},
                clear=False,
            ),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            check_audio_setup()


class AudioCaptureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.helper = Path(self.temp_dir.name) / "audio-helper"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_helper(self, body: str) -> None:
        self.helper.write_text(
            f"#!/usr/bin/env python3\n{body}",
            encoding="utf-8",
        )
        self.helper.chmod(self.helper.stat().st_mode | stat.S_IXUSR)

    def test_streams_whisper_ready_chunks_and_stops_helper(self) -> None:
        self._write_helper(
            """\
import struct
import sys
import time

sys.stdout.buffer.write(b"TRNEAUD1")
sys.stdout.buffer.write(struct.pack("<f", 0.25) * 16_000)
sys.stdout.buffer.flush()
time.sleep(60)
"""
        )
        capture = AudioCapture(chunk_seconds=1, helper_path=self.helper)

        try:
            capture.start()
            deadline = time.monotonic() + 3.0
            chunk = None
            while chunk is None and time.monotonic() < deadline:
                chunk = capture.get_chunk()
                time.sleep(0.01)

            self.assertIsNotNone(chunk)
            assert chunk is not None
            self.assertEqual(chunk.dtype, np.float32)
            self.assertEqual(chunk.shape, (16_000,))
            np.testing.assert_allclose(chunk, 0.25)
        finally:
            capture.stop()

    def test_rejects_invalid_helper_stream(self) -> None:
        self._write_helper(
            """\
import sys

sys.stdout.buffer.write(b"BADMAGIC")
sys.stdout.buffer.flush()
"""
        )
        capture = AudioCapture(chunk_seconds=1, helper_path=self.helper)

        with self.assertRaisesRegex(RuntimeError, "invalid stream header"):
            capture.start()


if __name__ == "__main__":
    unittest.main()
