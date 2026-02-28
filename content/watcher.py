"""Periodic screenshot capture loop during content-watching phase."""

from __future__ import annotations

import asyncio

from playwright.async_api import Page

from browser.screenshot import capture_base64_jpeg, is_duplicate_frame
from browser.video_probe import get_video_state


async def capture_content_frame(
    page: Page,
    vlm,
    accumulator,
    last_b64: str | None,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """
    Capture one screenshot, skip if it's a near-duplicate of the previous frame,
    describe it with the VLM, and add it to the accumulator.

    Returns the base64 of the captured frame (for duplicate detection next round).
    """
    b64 = await capture_base64_jpeg(page)

    if is_duplicate_frame(b64, last_b64):
        return last_b64  # Nothing new to analyze

    context_summary = accumulator.get_summary()

    # VLM call is synchronous — run in executor to avoid blocking the event loop
    description = await loop.run_in_executor(
        None, vlm.describe_frame, b64, context_summary
    )
    print(f"[watcher] Frame described: {description[:120]}...")
    await accumulator.add_frame(description, loop)

    return b64


async def is_content_active(page: Page) -> bool:
    """
    Returns True if a video is actively playing on the current page.
    Used to decide whether to keep capturing frames or move on.
    """
    state = await get_video_state(page)
    if state is None:
        return False
    return not state["paused"] and not state["ended"]
