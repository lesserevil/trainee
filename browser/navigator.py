"""Page navigation utilities: advance through course pages."""

from playwright.async_api import Page

# Common selectors for "next page" / "continue" buttons across LMS platforms
_ADVANCE_SELECTORS = [
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Proceed')",
    "a:has-text('Next')",
    "a:has-text('Continue')",
    ".next-button",
    ".btn-next",
    ".course-next",
    "[aria-label='Next']",
    "[aria-label='Continue']",
    "[data-action='next']",
    "[data-action='continue']",
    # Articulate Storyline
    ".slide-object-next",
    # iSpring
    ".ft-btn-next",
    # Moodle
    "#mod_scorm_navnext",
    ".mod_scorm-display-inline a[title='Next']",
]


async def try_advance_page(page: Page) -> bool:
    """
    Attempt to click a 'next' or 'continue' button to advance the course.
    Returns True if a button was found and clicked.
    """
    for selector in _ADVANCE_SELECTORS:
        try:
            btn = page.locator(selector)
            if await btn.count() > 0:
                first = btn.first
                if await first.is_visible():
                    await first.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    return True
        except Exception:
            continue

    # Also check inside accessible iframes
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for selector in _ADVANCE_SELECTORS:
            try:
                btn = frame.locator(selector)
                if await btn.count() > 0:
                    first = btn.first
                    if await first.is_visible():
                        await first.click()
                        return True
            except Exception:
                continue

    return False
