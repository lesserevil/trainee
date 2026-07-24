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

- macOS 14.2 or newer
- Python 3.12 with [uv](https://github.com/astral-sh/uv)
- Xcode Command Line Tools
- An NVIDIA API key in `BUILD_NVIDIA_COM_API_TOKEN`
- Playwright Chromium

The default model runs through NVIDIA's hosted API, so no local GPU is required
for model inference. System audio is captured with a private native Core Audio
process tap. Your selected speakers or headphones continue to work normally;
no virtual audio driver or Multi-Output Device is required.

Python `>=3.10` is allowed by package metadata, but the documented setup uses
Python 3.12 because that is the path this project is exercised against.

## Quick Start

From a fresh checkout, run:

```bash
make setup
```

The setup target creates a Python 3.12 virtual environment, installs `trainee`
with audio support, installs Playwright Chromium, and builds the native macOS
audio-capture helper. It is safe to run again when refreshing an existing
checkout.

At the end, it prints the remaining manual steps. Create an API key at
[build.nvidia.com](https://build.nvidia.com), then export it:

```bash
export BUILD_NVIDIA_COM_API_TOKEN="nvapi-..."
```

Start a course:

```bash
source .venv/bin/activate
trainee --url "https://example.com/course/module1"
```

The browser opens with a persistent profile in `.browser-profile`. On a managed
Mac with Company Portal installed, `trainee` downloads the Microsoft Single
Sign On extension from the Chrome Web Store into that profile and connects it
to the Company Portal browser broker. Log in, accept any terms, navigate to the
start of the course, then press Enter in the terminal when you want `trainee`
to begin watching.

The first time native capture starts, macOS asks whether `trainee Audio Capture`
may record system audio. Allow it to continue. This is the only manual audio
setup step.

Each run writes a live Markdown knowledge base under `knowledge/`. The file is
updated as frames and audio transcripts are captured, so you can inspect it
during periodic quizzes and review it after the run.

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

# Write the knowledge base to a specific file
python trainee.py --url "https://example.com/course/module1" \
  --knowledge-file knowledge/compliance-course.md
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
| `--no-microsoft-sso` | `False` | Disable Microsoft SSO extension setup |
| `--max-iterations` | `500` | Safety limit on main loop iterations |
| `--knowledge-dir` | `knowledge` | Directory for per-run Markdown knowledge base files |
| `--knowledge-file` | unset | Write the run knowledge base to a specific Markdown file |
| `--no-knowledge-base` | `False` | Disable Markdown knowledge base output |
| `--no-audio` | `False` | Diagnostic mode that disables required audio capture |

## Knowledge Base Output

By default, each run creates a timestamped Markdown file:

```text
knowledge/trainee-YYYYMMDD-HHMMSSZ.md
```

The file is updated throughout the run. It includes:

- run metadata, including URL, model backend, model ID, and status
- the current quiz context that `trainee` sends to the model
- the compressed course summary
- recent uncompressed visual notes and audio transcript chunks
- appendices with all captured visual notes and audio transcript segments

Generated knowledge base files are ignored by git. They are intended as local
run artifacts for live inspection and post-run review.

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

Native system audio capture requires macOS 14.2 or newer. If `trainee` reports
that its helper is missing, rebuild it:

```bash
make build
```

If capture starts but course narration is silent, open **System Settings >
Privacy & Security**, enable system-audio recording for `trainee Audio Capture`,
then restart `trainee`. The exact privacy-panel name varies slightly by macOS
release.

For a visual-only diagnostic run:

```bash
python trainee.py --url "https://example.com/course/module1" --no-audio
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

### Microsoft SSO Is Unavailable

On macOS, `trainee` configures its dedicated browser profile with Microsoft's
Chrome SSO extension. This requires:

- Microsoft Company Portal and its BrowserCore native messaging host
- A managed Mac registered for Microsoft Platform SSO

When those prerequisites are present, the extension is downloaded from the
Chrome Web Store on browser startup and loaded into Playwright Chromium. If the
prerequisites are missing, `trainee` prints a warning and continues without
Microsoft SSO.

## Project Structure

```text
trainee/
├── trainee.py           # CLI entry point and orchestration loop
├── config.py            # Configuration dataclass
├── browser/             # Playwright browser control, navigation, screenshots
├── content/             # Screenshot watching, audio capture, transcription
├── native/              # Core Audio process-tap helper
├── model/               # Vision-language model interface and prompts
├── quiz/                # Quiz detection, extraction, and answering
└── context/             # Rolling context accumulator
```
