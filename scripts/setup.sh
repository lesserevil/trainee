#!/bin/sh

set -eu

project_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

say() {
    printf '%s\n' "$1"
}

say "[setup] Checking required tools"
if ! command -v uv >/dev/null 2>&1; then
    say ""
    say "uv is required but was not found."
    say "Install it from https://docs.astral.sh/uv/getting-started/installation/"
    say "Then run: make setup"
    exit 1
fi

if [ -x .venv/bin/python ]; then
    say "[setup] Python environment already exists at .venv"
else
    say "[setup] Creating a Python 3.12 environment at .venv"
    uv venv --python 3.12 .venv
fi

say "[setup] Installing trainee with audio support"
uv pip install --python .venv/bin/python -e ".[audio]"

say "[setup] Downloading required local models"
.venv/bin/python scripts/download_models.py

say "[setup] Installing Playwright Chromium"
.venv/bin/python -m playwright install chromium

platform=$(uname -s)

if [ "$platform" = "Darwin" ]; then
    say "[setup] Building native macOS system audio capture"
    sh scripts/build_audio_helper.sh
fi

say ""
say "Automated setup is complete."
say ""
say "Manual steps:"

if [ -z "${BUILD_NVIDIA_COM_API_TOKEN:-}" ]; then
    say "  1. Create an NVIDIA API key at https://build.nvidia.com/ and export it:"
    say "       export BUILD_NVIDIA_COM_API_TOKEN=\"nvapi-...\""
else
    say "  1. BUILD_NVIDIA_COM_API_TOKEN is set for this shell."
fi

if [ "$platform" = "Darwin" ]; then
    say "  2. On the first course run, allow trainee Audio Capture"
    say "     to record system audio when macOS asks."
    say "     Your current speakers or headphones stay selected."
else
    say "  2. Native system audio capture requires macOS 14.2 or newer."
    say "     Use --no-audio for a visual-only diagnostic run on this platform."
fi

say ""
say "Run trainee with:"
say "  source .venv/bin/activate"
say "  trainee --url \"https://your-course-url\""
