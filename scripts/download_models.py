#!/usr/bin/env python3
"""Download the local model artifacts required by the default installation."""

from pathlib import Path
import sys

from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DEFAULT_WHISPER_MODEL_SIZE  # noqa: E402


WHISPER_REPOSITORIES = {
    "large-v3": "Systran/faster-whisper-large-v3",
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
        f"[models] Downloading Whisper {DEFAULT_WHISPER_MODEL_SIZE} "
        "(this can take several minutes)..."
    )
    model_path = snapshot_download(
        repo_id=repository,
        allow_patterns=list(WHISPER_FILES),
    )
    print(f"[models] Whisper {DEFAULT_WHISPER_MODEL_SIZE} ready at {model_path}")


if __name__ == "__main__":
    main()
