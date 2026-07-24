import sys
import types
import unittest
from unittest.mock import Mock, patch

from content.transcriber import Transcriber


class TranscriberTest(unittest.TestCase):
    def _faster_whisper_modules(
        self,
        *,
        model_path: str = "/cache/faster-whisper-large-v3",
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

    def test_eagerly_loads_whisper_from_the_local_cache(self) -> None:
        modules, whisper_model, download_model = self._faster_whisper_modules()

        with patch.dict(sys.modules, modules):
            transcriber = Transcriber("large-v3")

        download_model.assert_called_once_with(
            "large-v3",
            local_files_only=True,
        )
        whisper_model.assert_called_once_with(
            "/cache/faster-whisper-large-v3",
            device="auto",
            compute_type="auto",
        )
        self.assertIs(transcriber._model, whisper_model.return_value)

    def test_reports_when_setup_has_not_downloaded_the_model(self) -> None:
        modules, whisper_model, _ = self._faster_whisper_modules(
            download_error=OSError("cache miss")
        )

        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(RuntimeError, "Run `make setup`"):
                Transcriber("large-v3")

        whisper_model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
