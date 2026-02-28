# trainee

AI-powered course taker. Watches browser-based training courses in real time and answers quizzes automatically using a local vision-language model.

## How it works

1. Opens a browser and waits for you to log in and navigate to the course
2. Watches the course content (video or slides) by taking periodic screenshots
3. Builds a rolling summary of what's been covered using a local VLM
4. Detects quizzes automatically and answers them based on the accumulated context
5. Advances through slides and pages as content completes

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Playwright (Chromium)
- One of:
  - Apple Silicon Mac (MLX backend)
  - NVIDIA GPU with CUDA (vLLM backend)
- Optional: [BlackHole](https://existential.audio/blackhole/) virtual audio device for audio capture (macOS)

## Installation

```bash
uv venv --python 3.12
source .venv/bin/activate

# Apple Silicon
uv pip install -e ".[mlx,audio]"

# NVIDIA CUDA
uv pip install -e ".[vllm,audio]"

playwright install chromium
```

## Usage

```bash
# Basic usage
python trainee.py --url "https://example.com/course/module1"

# With options
python trainee.py --url "..." --backend mlx --interval 2.0 --headless

# Or via the installed script
trainee --url "https://example.com/course/module1"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | *(required)* | URL of the training course |
| `--backend` | `auto` | Model backend: `auto`, `vllm` (NVIDIA), `mlx` (Apple Silicon) |
| `--model` | `Qwen/Qwen2-VL-7B-Instruct` | HuggingFace model ID |
| `--interval` | `3.0` | Screenshot interval in seconds |
| `--no-audio` | — | Disable audio capture |
| `--whisper-model` | `large-v3` | faster-whisper model size |
| `--headless` | — | Run browser in headless mode |
| `--max-iterations` | `500` | Safety limit on main loop iterations |

## Audio setup (optional)

Audio capture uses BlackHole to record system audio and transcribe it with faster-whisper. This gives the model spoken narration as additional context alongside screenshots.

Audio is enabled by default when the `audio` extra is installed. Use `--no-audio` to disable it.

### Manual setup (macOS)

**1. Install BlackHole 2ch**

```bash
brew install blackhole-2ch
```

If you don't have Homebrew, install it from https://brew.sh first. After installing BlackHole, you may need to restart your Mac before it appears as an audio device.

**2. Create a Multi-Output Device**

Open **Audio MIDI Setup** (Spotlight → "Audio MIDI Setup"), then:

1. Click the **+** button at the bottom-left and choose **Create Multi-Output Device**
2. In the right pane, check **BlackHole 2ch** and your speakers (e.g. "MacBook Pro Speakers" or "External Headphones")
3. Enable **Drift Correction** for **BlackHole 2ch** only — leave it unchecked for your speakers. This keeps the virtual device in sync with the real hardware clock.
4. Double-click the new device name and rename it to **trainee Multi-Output**

**3. Set it as the system output**

Open **System Settings → Sound → Output** and select **trainee Multi-Output**.

Your audio will now play through your speakers and be captured by trainee at the same time.

## Project structure

```
trainee/
├── trainee.py           # CLI entry point and main orchestration loop
├── config.py            # Configuration dataclass
├── browser/             # Playwright browser control, navigation, screenshots
├── content/             # Screenshot watcher, audio capture, transcription
├── model/               # Vision-language model interface and prompts
├── quiz/                # Quiz detection, extraction, and answering
└── context/             # Rolling context accumulator
```
