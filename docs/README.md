# Documentation

Start with the top-level [README](../README.md). It is the canonical setup and
operating guide for this project.

## Current Docs

- [Project quick start and troubleshooting](../README.md)

## Important Setup Notes

The default model backend is NVIDIA's hosted API at
`https://integrate.api.nvidia.com/v1` using
`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`. Users need an API key from
build.nvidia.com in `BUILD_NVIDIA_COM_API_TOKEN`.

Audio capture is a required part of normal operation. On macOS 14.2 or newer,
`trainee` uses a native Core Audio process tap. It does not require BlackHole,
a Multi-Output Device, or changing the selected sound output.

`make setup` downloads the default Whisper `small` model. On Apple Silicon it
caches both MLX and faster-whisper formats; other systems cache the portable
faster-whisper format. Runtime automatically prefers MLX when available, loads
only from the local Hugging Face cache, and warms the model before audio capture
starts.

The first capture run displays macOS's system-audio recording permission prompt
for `trainee Audio Capture`. The user must allow it before narration can be
captured.

Each run writes a live Markdown knowledge base under `knowledge/` by default.
That generated directory is ignored by git and is meant for live quiz inspection
and post-run review.

Use `--no-audio` only for diagnostic visual-only runs, such as checking
Playwright browser startup or model loading before completing audio setup.

## Keeping Docs In Sync

Update the README whenever setup commands, runtime requirements, supported
hardware, CLI flags, or audio setup behavior changes.
