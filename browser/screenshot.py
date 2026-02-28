"""Screenshot capture and base64 encoding."""

import base64

from playwright.async_api import Page


async def capture_base64_jpeg(page: Page, quality: int = 75) -> str:
    """Return a base64-encoded JPEG screenshot of the current viewport."""
    raw = await page.screenshot(type="jpeg", quality=quality, full_page=False)
    return base64.b64encode(raw).decode("utf-8")


def is_duplicate_frame(b64_new: str, b64_prev: str | None, tolerance: int = 200) -> bool:
    """
    Cheap duplicate detection: compare encoded byte lengths.
    Frames that differ by fewer than `tolerance` bytes are considered duplicates.
    This avoids re-sending identical still frames to the VLM.
    """
    if b64_prev is None:
        return False
    return abs(len(b64_new) - len(b64_prev)) < tolerance
