import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

from content.transcriber import (
    Transcriber,
    _FasterWhisperBackend,
    _MLXWhisperBackend,
    _mlx_runtime_available,
)


class TranscriberTest(unittest.TestCase):
    def _faster_whisper_modules(
        self,
        *,
        model_path: str = "/cache/faster-whisper-small",
        download_error: Exception | None = None,
    ) -> tuple[dict[str, types.ModuleType], Mock, Mock]:
        whisper_model = Mock()
        download_model = Mock(
            return_value=model_path,
            side_effect=download_error,
        )

        package = types.ModuleType("faster_whisper")
        package.WhisperModel = whisper_model
        utils = types.ModuleType("faster_whisper.utils")
        utils.download_model = download_model
        return (
            {
                "faster_whisper": package,
                "faster_whisper.utils": utils,
            },
            whisper_model,
            download_model,
        )

    def test_detects_mlx_runtime_on_apple_silicon(self) -> None:
        with (
            patch("content.transcriber.platform.system", return_value="Darwin"),
            patch("content.transcriber.platform.machine", return_value="arm64"),
            patch.object(importlib, "import_module") as import_module,
        ):
            self.assertTrue(_mlx_runtime_available())

        import_module.assert_called_once_with("mlx_whisper")

    def test_mlx_runtime_is_unavailable_when_import_fails(self) -> None:
        with (
            patch("content.transcriber.platform.system", return_value="Darwin"),
            patch("content.transcriber.platform.machine", return_value="arm64"),
            patch.object(
                importlib,
                "import_module",
                side_effect=ImportError("mlx-whisper is not installed"),
            ),
        ):
            self.assertFalse(_mlx_runtime_available())

    def test_mlx_runtime_is_unavailable_on_other_platforms(self) -> None:
        with (
            patch("content.transcriber.platform.system", return_value="Linux"),
            patch.object(importlib, "import_module") as import_module,
        ):
            self.assertFalse(_mlx_runtime_available())

        import_module.assert_not_called()

    def test_automatically_uses_mlx_when_available(self) -> None:
        backend = Mock()
        backend.name = "mlx"

        with (
            patch("content.transcriber._mlx_runtime_available", return_value=True),
            patch(
                "content.transcriber._MLXWhisperBackend",
                return_value=backend,
            ) as mlx_backend,
            patch("content.transcriber._FasterWhisperBackend") as faster_backend,
        ):
            transcriber = Transcriber("small")

        mlx_backend.assert_called_once_with("small")
        faster_backend.assert_not_called()
        self.assertEqual(transcriber.backend_name, "mlx")

    def test_falls_back_to_faster_whisper_when_mlx_is_unavailable(self) -> None:
        backend = Mock()
        backend.name = "faster-whisper"

        with (
            patch("content.transcriber._mlx_runtime_available", return_value=False),
            patch("content.transcriber._MLXWhisperBackend") as mlx_backend,
            patch(
                "content.transcriber._FasterWhisperBackend",
                return_value=backend,
            ) as faster_backend,
        ):
            transcriber = Transcriber("small")

        mlx_backend.assert_not_called()
        faster_backend.assert_called_once_with("small")
        self.assertEqual(transcriber.backend_name, "faster-whisper")

    def test_eagerly_loads_and_warms_mlx_from_the_local_cache(self) -> None:
        transcribe = Mock(
            side_effect=[
                {"text": ""},
                {"text": "  locally transcribed  "},
            ]
        )
        mlx_whisper = types.ModuleType("mlx_whisper")
        mlx_whisper.transcribe = transcribe

        with (
            patch.dict(sys.modules, {"mlx_whisper": mlx_whisper}),
            patch(
                "huggingface_hub.snapshot_download",
                return_value="/cache/mlx-whisper-small",
            ) as snapshot_download,
        ):
            backend = _MLXWhisperBackend("small")
            text = backend.transcribe_chunk(
                np.ones(16_000, dtype=np.float32)
            )

        snapshot_download.assert_called_once_with(
            repo_id="mlx-community/whisper-small-mlx",
            allow_patterns=["config.json", "weights.npz"],
            local_files_only=True,
        )
        warmup = transcribe.call_args_list[0]
        np.testing.assert_array_equal(
            warmup.args[0],
            np.zeros(16_000, dtype=np.float32),
        )
        self.assertEqual(
            warmup.kwargs,
            {
                "path_or_hf_repo": "/cache/mlx-whisper-small",
                "language": "en",
                "temperature": 0.0,
                "verbose": None,
            },
        )
        self.assertEqual(text, "locally transcribed")

    def test_eagerly_loads_faster_whisper_from_the_local_cache(self) -> None:
        modules, whisper_model, download_model = self._faster_whisper_modules()

        with patch.dict(sys.modules, modules):
            backend = _FasterWhisperBackend("small")

        download_model.assert_called_once_with(
            "small",
            local_files_only=True,
        )
        whisper_model.assert_called_once_with(
            "/cache/faster-whisper-small",
            device="auto",
            compute_type="auto",
        )
        self.assertIs(backend._model, whisper_model.return_value)

    def test_reports_when_faster_whisper_model_is_not_cached(self) -> None:
        modules, whisper_model, _ = self._faster_whisper_modules(
            download_error=OSError("cache miss")
        )

        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(RuntimeError, "Run `make setup`"):
                _FasterWhisperBackend("small")

        whisper_model.assert_not_called()

    def test_reports_when_mlx_model_is_not_cached(self) -> None:
        mlx_whisper = types.ModuleType("mlx_whisper")
        mlx_whisper.transcribe = Mock()

        with (
            patch.dict(sys.modules, {"mlx_whisper": mlx_whisper}),
            patch(
                "huggingface_hub.snapshot_download",
                side_effect=OSError("cache miss"),
            ),
            self.assertRaisesRegex(RuntimeError, "Run `make setup`"),
        ):
            _MLXWhisperBackend("small")

        mlx_whisper.transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
