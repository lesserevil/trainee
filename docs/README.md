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

Audio capture is a required part of normal operation. The documented audio path
uses BlackHole 2ch and a macOS Multi-Output Device.

Use `--no-audio` only for diagnostic visual-only runs, such as checking
Playwright browser startup or model loading before completing audio setup.

## Keeping Docs In Sync

Update the README whenever setup commands, runtime requirements, supported
hardware, CLI flags, or audio setup behavior changes.
