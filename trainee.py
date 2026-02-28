"""trainee — AI-powered course taker.

Watches a browser-based training course in real time and answers quizzes
automatically using a local vision-language model (vLLM).

Usage:
    python trainee.py --url "https://example.com/course/module1"
    python trainee.py --url "..." --audio --interval 2.0 --headless
"""

from __future__ import annotations

import argparse
import asyncio

from browser.controller import BrowserController
from browser.navigator import try_advance_page
from browser.screenshot import capture_base64_jpeg
from browser.video_probe import get_video_state
from config import Config
from content.watcher import capture_content_frame, is_content_active
from content.audio_capture import check_audio_setup
from context.accumulator import ContextAccumulator
from model.vlm import VisionModel
from quiz.detector import detect_quiz
from quiz.extractor import extract_quiz
from quiz.solver import solve_and_click


async def run(url: str, config: Config) -> None:
    loop = asyncio.get_event_loop()

    # 0. Pre-flight check: audio setup must be complete before we do anything else
    if config.use_audio:
        check_audio_setup()

    # 1. Load VLM (blocking, runs in the current thread before we start async work)
    vlm = VisionModel.get(
        model_id=config.model_id,
        max_model_len=config.max_model_len,
        max_images=config.max_vllm_images_per_prompt,
        backend=config.backend,
    )

    # 2. Start browser
    browser = BrowserController(config)
    await browser.start(url)

    # Pause so the user can log in, accept terms, or navigate to the right page
    print("\n" + "=" * 60)
    print("  Browser is open and ready.")
    print("  Log in, accept any terms, and navigate to the start of the course.")
    print("  When you're ready for the AI to begin watching, press Enter here.")
    print("=" * 60)
    await loop.run_in_executor(None, input, "  > Press Enter to start... ")
    print()

    # 3. Optional audio capture
    audio_capture = None
    transcriber = None
    if config.use_audio:
        from content.audio_capture import AudioCapture
        from content.transcriber import Transcriber

        try:
            audio_capture = AudioCapture(chunk_seconds=config.audio_chunk_seconds)
            transcriber = Transcriber(model_size=config.whisper_model_size)
            audio_capture.start()
        except RuntimeError as e:
            print(f"[audio] Warning: {e}\nContinuing without audio capture.")
            audio_capture = None

    # 4. Context accumulator
    accumulator = ContextAccumulator(vlm, compress_every=config.compress_every_n_frames)

    print(f"\n[trainee] Starting course at: {url}")
    print("[trainee] Press Ctrl+C to stop.\n")

    last_b64: str | None = None
    iteration = 0

    try:
        while iteration < config.max_iterations:
            iteration += 1
            page = browser.page  # Always use the current active window

            # --- Drain audio queue ---
            if audio_capture and transcriber:
                chunk = audio_capture.get_chunk()
                if chunk is not None:
                    text = await loop.run_in_executor(
                        None, transcriber.transcribe_chunk, chunk
                    )
                    if text:
                        accumulator.add_transcript(text)

            # --- Check for quiz ---
            quiz_result = await detect_quiz(page)
            if quiz_result:
                print(f"\n[trainee] Quiz detected ({quiz_result['selector']})")
                frame = quiz_result["frame"]
                quiz_data = await extract_quiz(frame)

                question = quiz_data.get("questionText", "")
                options = quiz_data.get("options", [])

                if not options:
                    print("[trainee] Quiz detected but no options found — waiting...")
                    await asyncio.sleep(config.screenshot_interval)
                    continue

                b64 = await capture_base64_jpeg(page, config.screenshot_quality)
                solved = await solve_and_click(
                    frame, quiz_data, accumulator, vlm, b64, loop
                )
                if solved:
                    print(f"[trainee] Quiz answered. Waiting {config.post_quiz_wait}s...")
                    await asyncio.sleep(config.post_quiz_wait)
                else:
                    await asyncio.sleep(config.screenshot_interval)
                continue

            # --- Watch content (video or slides) ---
            video_state = await get_video_state(page)

            if video_state and not video_state["paused"] and not video_state["ended"]:
                # Video is actively playing
                last_b64 = await capture_content_frame(
                    page, vlm, accumulator, last_b64, loop
                )
                await asyncio.sleep(config.screenshot_interval)
                continue

            # Slides / text / paused video — capture once then try to advance
            last_b64 = await capture_content_frame(
                page, vlm, accumulator, last_b64, loop
            )

            advanced = await try_advance_page(page)
            if advanced:
                print("[trainee] Advanced to next page.")
                last_b64 = None  # Reset duplicate detection after navigation
                await asyncio.sleep(1.5)
            else:
                # Nothing to advance — wait and re-check (content may be loading)
                await asyncio.sleep(config.screenshot_interval)

    except KeyboardInterrupt:
        print("\n[trainee] Stopped by user.")

    finally:
        if audio_capture:
            audio_capture.stop()
        await browser.stop()

    # Print final accumulated context
    print("\n" + "=" * 60)
    print("[trainee] Session complete.")
    print(f"[trainee] Total frames analyzed: {accumulator.frame_count}")
    print("\n[trainee] Accumulated course knowledge:\n")
    print(accumulator.get_summary())
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="trainee — AI-powered course taker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url", required=True,
        help="URL of the training course to take",
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2-VL-7B-Instruct",
        help="HuggingFace model ID for the vision-language model",
    )
    parser.add_argument(
        "--no-audio", action="store_true",
        help="Disable audio capture (audio is on by default; requires BlackHole on macOS)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless mode (may break some LMS platforms)",
    )
    parser.add_argument(
        "--interval", type=float, default=3.0,
        help="Screenshot interval in seconds during content watching",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=500,
        help="Safety limit on main loop iterations",
    )
    parser.add_argument(
        "--whisper-model", default="large-v3",
        help="faster-whisper model size (e.g. tiny, base, medium, large-v3)",
    )
    parser.add_argument(
        "--backend", default="auto", choices=["auto", "vllm", "mlx"],
        help="Model backend: auto (detect), vllm (NVIDIA CUDA), mlx (Apple Silicon)",
    )
    args = parser.parse_args()

    config = Config(
        model_id=args.model,
        backend=args.backend,
        use_audio=not args.no_audio,
        headless=args.headless,
        screenshot_interval=args.interval,
        max_iterations=args.max_iterations,
        whisper_model_size=args.whisper_model,
    )

    asyncio.run(run(args.url, config))


if __name__ == "__main__":
    main()
