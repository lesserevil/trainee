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

say "[setup] Installing Playwright Chromium"
.venv/bin/python -m playwright install chromium

platform=$(uname -s)
blackhole_ready=false

if [ "$platform" = "Darwin" ]; then
    if command -v system_profiler >/dev/null 2>&1 \
        && system_profiler SPAudioDataType 2>/dev/null \
        | grep -Fq "BlackHole 2ch"; then
        blackhole_ready=true
    elif command -v brew >/dev/null 2>&1 \
        && brew list --cask blackhole-2ch >/dev/null 2>&1; then
        blackhole_ready=true
    fi

    if [ "$blackhole_ready" = true ]; then
        say "[setup] BlackHole 2ch is already installed"
    elif command -v brew >/dev/null 2>&1; then
        say "[setup] Installing BlackHole 2ch"
        HOMEBREW_NO_AUTO_UPDATE=1 NONINTERACTIVE=1 \
            brew install --cask blackhole-2ch
        blackhole_ready=true
    else
        say "[setup] Homebrew is not installed; BlackHole requires manual installation"
    fi
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
    if [ "$blackhole_ready" = false ]; then
        say "  2. Install Homebrew, then install BlackHole:"
        say "       brew install --cask blackhole-2ch"
    else
        say "  2. Open Audio MIDI Setup and create a Multi-Output Device:"
        say "       - Select BlackHole 2ch and your speakers or headphones."
        say "       - Enable Drift Correction for BlackHole 2ch only."
        say "       - Select the Multi-Output Device in System Settings > Sound > Output."
    fi
else
    say "  2. Audio capture currently requires macOS and the BlackHole 2ch device."
    say "     Use --no-audio for a visual-only diagnostic run on this platform."
fi

say ""
say "Run trainee with:"
say "  source .venv/bin/activate"
say "  trainee --url \"https://your-course-url\""
