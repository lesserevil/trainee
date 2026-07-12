# trainee

AI-powered course taker. `trainee` opens a browser, watches a training course,
captures screenshots and system audio, builds a rolling course summary with a
local vision-language model, and answers quizzes from that accumulated context.

## Supported Setup

The intended setup is:

- macOS on Apple Silicon, using the MLX backend
- Python 3.12 with [uv](https://github.com/astral-sh/uv)
- Playwright Chromium
- BlackHole 2ch configured as a system-audio capture device

The package also contains a vLLM backend for NVIDIA CUDA machines, but the
current audio capture implementation expects the macOS BlackHole device named
`BlackHole 2ch`. A full non-macOS setup needs an equivalent audio-capture
implementation or a compatible device layer.

Python `>=3.10` is allowed by package metadata, but the documented setup uses
Python 3.12 because that is the path this project is exercised against.

## Quick Start

Run these commands from a fresh checkout:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[mlx,audio]"
playwright install chromium
```

Install BlackHole:

```bash
brew install blackhole-2ch
```

Then configure macOS audio:

1. Open **Audio MIDI Setup**.
2. Click **+** and choose **Create Multi-Output Device**.
3. Check **BlackHole 2ch** and your normal speakers or headphones.
4. Enable **Drift Correction** for **BlackHole 2ch** only.
5. Rename the device to something recognizable, such as `trainee Multi-Output`.
6. Open **System Settings > Sound > Output** and select that Multi-Output
   Device.

Start a course:

```bash
python trainee.py --url "https://example.com/course/module1" --backend mlx
```

The browser opens with a persistent profile in `.browser-profile`. Log in,
accept any terms, navigate to the start of the course, then press Enter in the
terminal when you want `trainee` to begin watching.

The first model load may take several minutes because the model weights need to
download and initialize.

## NVIDIA Backend

For CUDA machines, install the vLLM extra instead of MLX:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[vllm,audio]"
playwright install chromium
```

Run with:

```bash
python trainee.py --url "https://example.com/course/module1" --backend vllm
```

This backend still uses the same audio preflight. Today that preflight expects
BlackHole-style audio capture, so treat the CUDA path as model-backend support
unless you have also provided a compatible system-audio capture device.

## Usage

```bash
# Normal Apple Silicon run with required audio capture
python trainee.py --url "https://example.com/course/module1" --backend mlx

# Installed console script
trainee --url "https://example.com/course/module1" --backend mlx

# Diagnostic visual-only run
python trainee.py --url "https://example.com/course/module1" --backend mlx --no-audio
```

`--no-audio` is useful for checking browser automation or model setup, but it is
not the intended operating mode. Course narration is part of the context the
agent uses to answer quizzes.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | URL of the training course |
| `--backend` | `auto` | Model backend: `auto`, `vllm`, or `mlx` |
| `--model` | `Qwen/Qwen2-VL-7B-Instruct` | Hugging Face model ID |
| `--interval` | `3.0` | Screenshot interval in seconds |
| `--whisper-model` | `large-v3` | faster-whisper model size |
| `--headless` | `False` | Run browser in headless mode |
| `--max-iterations` | `500` | Safety limit on main loop iterations |
| `--no-audio` | `False` | Diagnostic mode that disables required audio capture |

## How It Works

1. Opens Chromium with a persistent browser profile.
2. Waits for you to log in and navigate to the course.
3. Captures screenshots and system audio while course content plays.
4. Transcribes audio with faster-whisper.
5. Builds a rolling summary using the local VLM.
6. Detects quizzes, extracts the prompt and options, and answers from the
   accumulated context.
7. Advances through slides and pages as content completes.

## Troubleshooting

### Audio Setup Is Incomplete

`trainee` checks audio before loading the model. If it reports missing
BlackHole or a missing Multi-Output Device, complete the BlackHole setup above
and make the Multi-Output Device your current macOS output device.

For a visual-only diagnostic run:

```bash
python trainee.py --url "https://example.com/course/module1" --backend mlx --no-audio
```

### `sounddevice` Is Missing

Install the audio extra for your backend:

```bash
uv pip install -e ".[mlx,audio]"
```

or:

```bash
uv pip install -e ".[vllm,audio]"
```

### Chromium Is Missing

If Playwright says the browser executable does not exist, install Chromium:

```bash
playwright install chromium
```

### Wrong Backend Dependency

If `mlx_vlm` is missing, install the MLX extra:

```bash
uv pip install -e ".[mlx,audio]"
```

If `vllm` is missing, install the vLLM extra:

```bash
uv pip install -e ".[vllm,audio]"
```

### Browser Login State Is Stale

Browser cookies and SSO state live in `.browser-profile`. To reset the browser
profile:

```bash
rm -rf .browser-profile
```

## Project Structure

```text
trainee/
├── trainee.py           # CLI entry point and orchestration loop
├── config.py            # Configuration dataclass
├── browser/             # Playwright browser control, navigation, screenshots
├── content/             # Screenshot watching, audio capture, transcription
├── model/               # Vision-language model interface and prompts
├── quiz/                # Quiz detection, extraction, and answering
└── context/             # Rolling context accumulator
```
