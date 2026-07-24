import unittest
from unittest.mock import Mock, call, patch

from scripts import download_models


class DownloadModelsTest(unittest.TestCase):
    @patch("scripts.download_models.platform.machine", return_value="arm64")
    @patch("scripts.download_models.platform.system", return_value="Darwin")
    @patch("scripts.download_models.snapshot_download")
    def test_downloads_both_required_whisper_snapshots_on_apple_silicon(
        self,
        snapshot_download: Mock,
        _system: Mock,
        _machine: Mock,
    ) -> None:
        snapshot_download.side_effect = [
            "/cache/faster-whisper-small",
            "/cache/mlx-whisper-small",
        ]

        download_models.main()

        self.assertEqual(
            snapshot_download.call_args_list,
            [
                call(
                    repo_id="Systran/faster-whisper-small",
                    allow_patterns=list(download_models.WHISPER_FILES),
                ),
                call(
                    repo_id="mlx-community/whisper-small-mlx",
                    allow_patterns=list(download_models.MLX_WHISPER_FILES),
                ),
            ],
        )

    @patch("scripts.download_models.platform.system", return_value="Linux")
    @patch("scripts.download_models.snapshot_download")
    def test_downloads_only_the_portable_model_on_other_platforms(
        self,
        snapshot_download: Mock,
        _system: Mock,
    ) -> None:
        snapshot_download.return_value = "/cache/faster-whisper-small"

        download_models.main()

        snapshot_download.assert_called_once_with(
            repo_id="Systran/faster-whisper-small",
            allow_patterns=list(download_models.WHISPER_FILES),
        )


if __name__ == "__main__":
    unittest.main()
