"""Page navigation utilities: advance through course pages."""

from playwright.async_api import Page

# Common selectors for "next page" / "continue" buttons across LMS platforms.
# Ordered from most-specific to broadest to avoid mis-clicking unrelated elements.
_ADVANCE_SELECTORS = [
    # Standard button elements
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Proceed')",
    "button:has-text('Next Page')",
    "button:has-text('Next Slide')",
    "button:has-text('Next Module')",
    "button:has-text('Go to Next')",
    # Anchor links used as buttons
    "a:has-text('Next')",
    "a:has-text('Continue')",
    # ARIA role=button elements (common in JS-heavy LMSes)
    "[role='button']:has-text('Next')",
    "[role='button']:has-text('Continue')",
    "[role='button']:has-text('Proceed')",
    # Input-type buttons
    "input[type='button'][value='Next']",
    "input[type='button'][value='Continue']",
    # ARIA labels (exact match)
    "[aria-label='Next']",
    "[aria-label='Continue']",
    # Title attributes
    "[title='Next']",
    "[title='Continue']",
    # Class/ID patterns
    ".next-button",
    ".btn-next",
    ".course-next",
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
    Returns True if a button was found, is visible, is enabled, and was clicked.
    """
    for selector in _ADVANCE_SELECTORS:
        try:
            btn = page.locator(selector)
            if await btn.count() > 0:
                first = btn.first
                if await first.is_visible() and await first.is_enabled():
                    await first.click()
                    print(f"[navigator] Clicked next button: {selector}")
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
                    if await first.is_visible() and await first.is_enabled():
                        await first.click()
                        print(f"[navigator] Clicked next button in iframe: {selector}")
                        return True
            except Exception:
                continue

    return False
