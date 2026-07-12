# Documentation

Start with the top-level [README](../README.md). It is the canonical setup and
operating guide for this project.

## Current Docs

- [Project quick start and troubleshooting](../README.md)

## Important Setup Notes

Audio capture is a required part of normal operation. The documented supported
path is macOS on Apple Silicon with BlackHole 2ch, a Multi-Output Device, and
the MLX backend.

Use `--no-audio` only for diagnostic visual-only runs, such as checking
Playwright browser startup or model loading before completing audio setup.

## Keeping Docs In Sync

Update the README whenever setup commands, runtime requirements, supported
hardware, CLI flags, or audio setup behavior changes.
