#!/usr/bin/env python3
"""Download the local model artifacts required by the default installation."""

from pathlib import Path
import platform
import sys

from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DEFAULT_WHISPER_MODEL_SIZE  # noqa: E402
from content.transcriber import (  # noqa: E402
    MLX_WHISPER_FILES,
    MLX_WHISPER_REPOSITORIES,
)


WHISPER_REPOSITORIES = {
    "small": "Systran/faster-whisper-small",
}
WHISPER_FILES = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)
def main() -> None:
    try:
        repository = WHISPER_REPOSITORIES[DEFAULT_WHISPER_MODEL_SIZE]
    except KeyError as error:
        raise RuntimeError(
            "No setup-time download is configured for the default Whisper model "
            f"{DEFAULT_WHISPER_MODEL_SIZE!r}"
        ) from error

    print(
        f"[models] Downloading faster-whisper {DEFAULT_WHISPER_MODEL_SIZE} "
        "(this can take several minutes)..."
    )
    model_path = snapshot_download(
        repo_id=repository,
        allow_patterns=list(WHISPER_FILES),
    )
    print(
        f"[models] faster-whisper {DEFAULT_WHISPER_MODEL_SIZE} "
        f"ready at {model_path}"
    )

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        mlx_repository = MLX_WHISPER_REPOSITORIES[DEFAULT_WHISPER_MODEL_SIZE]
        print(
            f"[models] Downloading MLX Whisper {DEFAULT_WHISPER_MODEL_SIZE} "
            "(this can take several minutes)..."
        )
        mlx_model_path = snapshot_download(
            repo_id=mlx_repository,
            allow_patterns=list(MLX_WHISPER_FILES),
        )
        print(
            f"[models] MLX Whisper {DEFAULT_WHISPER_MODEL_SIZE} "
            f"ready at {mlx_model_path}"
        )


if __name__ == "__main__":
    main()
