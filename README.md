# trainee

AI-powered course taker. `trainee` opens a browser, watches a training course,
captures screenshots and system audio, builds a rolling course summary with a
vision-language model, and answers quizzes from that accumulated context.

## Default Model

The default model is NVIDIA's hosted
`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` model through the
OpenAI-compatible NVIDIA API endpoint:

```text
https://integrate.api.nvidia.com/v1
```

You need an NVIDIA API key from [build.nvidia.com](https://build.nvidia.com).
Set it in the environment as `BUILD_NVIDIA_COM_API_TOKEN` before running `trainee`.

## Supported Setup

The intended setup is:

- Python 3.12 with [uv](https://github.com/astral-sh/uv)
- An NVIDIA API key in `BUILD_NVIDIA_COM_API_TOKEN`
- Playwright Chromium
- BlackHole 2ch configured as a system-audio capture device

The default model runs through NVIDIA's hosted API, so no local GPU is required
for model inference. The current audio capture implementation still expects the
macOS BlackHole device named `BlackHole 2ch`.

Python `>=3.10` is allowed by package metadata, but the documented setup uses
Python 3.12 because that is the path this project is exercised against.

## Quick Start

Run these commands from a fresh checkout:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[audio]"
playwright install chromium
```

Create an API key at [build.nvidia.com](https://build.nvidia.com), then export
it:

```bash
export BUILD_NVIDIA_COM_API_TOKEN="nvapi-..."
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
python trainee.py --url "https://example.com/course/module1"
```

The browser opens with a persistent profile in `.browser-profile`. Log in,
accept any terms, navigate to the start of the course, then press Enter in the
terminal when you want `trainee` to begin watching.

## Usage

```bash
# Normal run with hosted NVIDIA model and required audio capture
python trainee.py --url "https://example.com/course/module1"

# Installed console script
trainee --url "https://example.com/course/module1"

# Override the hosted model
python trainee.py --url "https://example.com/course/module1" \
  --model "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

# Diagnostic visual-only run
python trainee.py --url "https://example.com/course/module1" --no-audio
```

`--no-audio` is useful for checking browser automation or model setup, but it is
not the intended operating mode. Course narration is part of the context the
agent uses to answer quizzes.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | URL of the training course |
| `--backend` | `nvidia` | Model backend: `nvidia`, `auto`, `vllm`, or `mlx` |
| `--model` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | Model ID |
| `--api-base-url` | `https://integrate.api.nvidia.com/v1` | OpenAI-compatible API base URL for the NVIDIA backend |
| `--api-key-env` | `BUILD_NVIDIA_COM_API_TOKEN` | Environment variable containing the NVIDIA API key |
| `--api-max-tokens` | `1024` | Maximum response tokens for hosted model calls |
| `--interval` | `3.0` | Screenshot interval in seconds |
| `--whisper-model` | `large-v3` | faster-whisper model size |
| `--headless` | `False` | Run browser in headless mode |
| `--max-iterations` | `500` | Safety limit on main loop iterations |
| `--no-audio` | `False` | Diagnostic mode that disables required audio capture |

## Local Backends

The hosted NVIDIA backend is the default. Local model backends are still
available for development or offline operation.

Apple Silicon MLX:

```bash
uv pip install -e ".[mlx,audio]"
python trainee.py --url "https://example.com/course/module1" \
  --backend mlx \
  --model "Qwen/Qwen2-VL-7B-Instruct"
```

NVIDIA CUDA with vLLM:

```bash
uv pip install -e ".[vllm,audio]"
python trainee.py --url "https://example.com/course/module1" \
  --backend vllm \
  --model "Qwen/Qwen2-VL-7B-Instruct"
```

`--backend auto` preserves the previous local hardware detection behavior: CUDA
uses vLLM, Apple Silicon uses MLX, and other machines fall back to vLLM.

## How It Works

1. Opens Chromium with a persistent browser profile.
2. Waits for you to log in and navigate to the course.
3. Captures screenshots and system audio while course content plays.
4. Transcribes audio with faster-whisper.
5. Builds a rolling summary using the configured VLM.
6. Detects quizzes, extracts the prompt and options, and answers from the
   accumulated context.
7. Advances through slides and pages as content completes.

## Troubleshooting

### NVIDIA API Key Is Missing

Create a key at [build.nvidia.com](https://build.nvidia.com), then export it:

```bash
export BUILD_NVIDIA_COM_API_TOKEN="nvapi-..."
```

To use a different environment variable name:

```bash
export MY_NVIDIA_KEY="nvapi-..."
python trainee.py --url "https://example.com/course/module1" \
  --api-key-env MY_NVIDIA_KEY
```

### Audio Setup Is Incomplete

`trainee` checks audio before loading the model. If it reports missing
BlackHole or a missing Multi-Output Device, complete the BlackHole setup above
and make the Multi-Output Device your current macOS output device.

For a visual-only diagnostic run:

```bash
python trainee.py --url "https://example.com/course/module1" --no-audio
```

### `sounddevice` Is Missing

Install the audio extra:

```bash
uv pip install -e ".[audio]"
```

For local backends, keep the matching backend extra:

```bash
uv pip install -e ".[mlx,audio]"
uv pip install -e ".[vllm,audio]"
```

### Chromium Is Missing

If Playwright says the browser executable does not exist, install Chromium:

```bash
playwright install chromium
```

### Local Backend Dependency Is Missing

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
