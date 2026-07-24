import unittest
from unittest.mock import Mock, patch

from scripts import download_models


class DownloadModelsTest(unittest.TestCase):
    @patch("scripts.download_models.snapshot_download")
    def test_downloads_the_required_whisper_snapshot(
        self,
        snapshot_download: Mock,
    ) -> None:
        snapshot_download.return_value = "/cache/faster-whisper-large-v3"

        download_models.main()

        snapshot_download.assert_called_once_with(
            repo_id="Systran/faster-whisper-large-v3",
            allow_patterns=list(download_models.WHISPER_FILES),
        )


if __name__ == "__main__":
    unittest.main()
