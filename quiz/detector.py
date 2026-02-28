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

FREE_TEXT_SELECTORS = [
    ".quiz-question input[type='text']",
    ".question-container input[type='text']",
    ".h5p-question input[type='text']",
    ".h5p-question textarea",
    ".h5p-text-input",
    ".h5p-fill-in input",
    ".ft-quiz input[type='text']",
    ".ft-quiz textarea",
    "input[type='text']",   # broad fallback, tried last
    "textarea",
]

_DETECT_JS = """
([mcSelectors, ftSelectors]) => {
    function check(doc, selectors, qType) {
        for (const sel of selectors) {
            try {
                const els = doc.querySelectorAll(sel);
                if (els.length > 0)
                    return { detected: true, selector: sel, count: els.length, questionType: qType };
            } catch (e) {}
        }
        return null;
    }
    function checkDoc(doc) {
        return check(doc, mcSelectors, 'multiple_choice') || check(doc, ftSelectors, 'free_text');
    }
    const main = checkDoc(document);
    if (main) return main;
    for (const iframe of Array.from(document.querySelectorAll('iframe'))) {
        try {
            const iDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iDoc) { const r = checkDoc(iDoc); if (r) return r; }
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
        return await frame.evaluate(_DETECT_JS, [QUIZ_SELECTORS, FREE_TEXT_SELECTORS])
    except Exception:
        return None
