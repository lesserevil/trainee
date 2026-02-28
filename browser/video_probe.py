"""JavaScript injection helpers to inspect video element state."""

import asyncio

from playwright.async_api import Page

# JS that finds the first video element in the main document or accessible iframes
_VIDEO_STATE_JS = """
() => {
    function findVideos(doc) {
        try {
            return Array.from(doc.querySelectorAll('video'));
        } catch (e) {
            return [];
        }
    }

    let videos = findVideos(document);

    // Walk accessible same-origin iframes
    const iframes = Array.from(document.querySelectorAll('iframe'));
    for (const iframe of iframes) {
        try {
            const iDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iDoc) {
                videos = videos.concat(findVideos(iDoc));
            }
        } catch (e) {
            // Cross-origin iframe — skip
        }
    }

    if (videos.length === 0) return null;

    const v = videos[0];
    return {
        currentTime: v.currentTime,
        duration: v.duration || 0,
        paused: v.paused,
        ended: v.ended,
        readyState: v.readyState,
        hasSrc: !!(v.src || v.querySelector('source')),
    };
}
"""


async def get_video_state(page: Page) -> dict | None:
    """Return video element state, or None if no video is present."""
    try:
        return await page.evaluate(_VIDEO_STATE_JS)
    except Exception:
        return None


async def wait_for_video_end(page: Page, poll_interval: float = 3.0) -> None:
    """Block until the primary video has ended, or return immediately if no video."""
    while True:
        state = await get_video_state(page)
        if state is None:
            return  # No video on this page
        if state["ended"]:
            return
        if state["duration"] > 0 and state["currentTime"] >= state["duration"] - 1.0:
            return
        await asyncio.sleep(poll_interval)
