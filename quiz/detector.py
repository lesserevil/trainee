"""DOM scanning to detect when a quiz is present on the current page."""

from __future__ import annotations

from playwright.async_api import Frame, Page

# Ordered list of CSS selectors that indicate quiz content.
# Checked from most-specific to most-generic.
QUIZ_SELECTORS = [
    # Standard HTML form controls
    "input[type='radio']",
    "input[type='checkbox']",
    # ARIA roles
    "[role='radio']",
    "[role='radiogroup']",
    "[role='checkbox']",
    # Common LMS class patterns
    ".quiz-question",
    ".question-container",
    ".mc-question",
    ".answer-option",
    ".quiz-answer",
    # H5P
    ".h5p-question",
    ".h5p-mc-question",
    ".h5p-question-content",
    # SCORM generic
    "#quiz",
    ".scorm-quiz",
    # Articulate Storyline
    ".slide-object-radio",
    # iSpring
    ".ft-quiz",
    # Button-based answer patterns
    "button[data-answer]",
    "li[data-answer]",
]

_DETECT_JS = """
(selectors) => {
    function check(doc, prefix) {
        for (const sel of selectors) {
            try {
                const els = doc.querySelectorAll(sel);
                if (els.length > 0) {
                    return { detected: true, selector: sel, count: els.length };
                }
            } catch (e) {}
        }
        return null;
    }

    // Check main document
    const main = check(document, '');
    if (main) return main;

    // Check accessible iframes
    const iframes = Array.from(document.querySelectorAll('iframe'));
    for (const iframe of iframes) {
        try {
            const iDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iDoc) {
                const result = check(iDoc, '');
                if (result) return result;
            }
        } catch (e) {}
    }

    return null;
}
"""


async def detect_quiz(page: Page) -> dict | None:
    """
    Scan the main page and all accessible iframes for quiz elements.

    Returns a dict with keys {detected, selector, count, frame} or None.
    The `frame` value is the Playwright Frame object where the quiz lives.
    """
    # Check main frame
    result = await _check_frame(page.main_frame)
    if result:
        result["frame"] = page.main_frame
        return result

    # Check sub-frames (SCORM / H5P iframes)
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        result = await _check_frame(frame)
        if result:
            result["frame"] = frame
            return result

    return None


async def _check_frame(frame: Frame) -> dict | None:
    try:
        return await frame.evaluate(_DETECT_JS, QUIZ_SELECTORS)
    except Exception:
        return None
