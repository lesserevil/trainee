"""Quiz solving: ask the VLM for an answer, then click and submit via Playwright."""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import Frame


async def solve_and_click(
    frame: Frame,
    quiz_data: dict,
    accumulator,
    vlm,
    base64_jpeg: str,
    loop: asyncio.AbstractEventLoop,
) -> bool:
    """
    Given extracted quiz data, ask the VLM which option(s) to pick,
    click them, and submit the quiz.

    Returns True if answers were successfully clicked.
    """
    question = quiz_data.get("questionText", "").strip()
    options = quiz_data.get("options", [])

    if not options:
        print("[solver] No answer options found — skipping.")
        return False

    if not question:
        print("[solver] No question text extracted — using screenshot context only.")
        question = "(Question text not detected — see screenshot)"

    option_labels = [opt["label"] or opt["value"] or f"Option {i+1}"
                     for i, opt in enumerate(options)]

    print(f"[solver] Question: {question[:120]}")
    for i, label in enumerate(option_labels):
        print(f"  {chr(65+i)}. {label}")

    # Ask the VLM
    context = accumulator.get_summary()
    raw_answer = await loop.run_in_executor(
        None, vlm.answer_quiz, base64_jpeg, question, option_labels, context
    )
    print(f"[solver] VLM answer: {raw_answer}")

    # Parse letter(s) from the response: e.g. "B" or "A, C"
    chosen_indices = _parse_answer_letters(raw_answer, len(options))
    if not chosen_indices:
        print("[solver] Could not parse answer letters from VLM response.")
        return False

    # Click the chosen options
    for idx in chosen_indices:
        opt = options[idx]
        print(f"[solver] Clicking option {chr(65+idx)}: {opt['label']}")
        await _click_option(frame, opt)

    # Submit the quiz
    await _submit_quiz(frame)
    return True


def _parse_answer_letters(response: str, num_options: int) -> list[int]:
    """
    Parse letter(s) like 'B' or 'A, C' or 'A and C' from the VLM response.
    Returns a list of 0-based indices.
    """
    # Find all capital letters A-Z in the response
    letters = re.findall(r'\b([A-Z])\b', response.upper())
    indices = []
    for letter in letters:
        idx = ord(letter) - ord('A')
        if 0 <= idx < num_options and idx not in indices:
            indices.append(idx)
    return indices


async def _click_option(frame: Frame, opt: dict) -> None:
    """Click or check the appropriate element for this answer option."""
    element_type = opt.get("elementType", "input")
    input_type = opt.get("inputType", "radio")
    opt_id = opt.get("id", "")
    label_text = opt.get("label", "").strip()

    try:
        if element_type == "input" and input_type in ("radio", "checkbox"):
            if opt_id:
                # Prefer clicking the label (more reliable than the hidden input)
                label = frame.locator(f"label[for='{opt_id}']")
                if await label.count() > 0:
                    await label.first.click()
                    return
                # Fall back to checking the input directly
                await frame.locator(f"#{opt_id}").check()
            elif label_text:
                await frame.get_by_label(label_text, exact=False).check()

        elif element_type == "aria":
            if opt_id:
                await frame.locator(f"#{opt_id}").click()
            elif label_text:
                await frame.get_by_text(label_text, exact=False).first.click()

        elif element_type == "button":
            if opt_id:
                await frame.locator(f"#{opt_id}").click()
            elif label_text:
                await frame.get_by_text(label_text, exact=False).first.click()

    except Exception as e:
        print(f"[solver] Warning: could not click option '{label_text}': {e}")


async def _submit_quiz(frame: Frame) -> None:
    """Attempt to click the quiz submit/check/next button."""
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Check')",
        "button:has-text('Check Answer')",
        "button:has-text('Confirm')",
        ".submit-button",
        ".h5p-check-button",
        "button:has-text('Next')",
        ".btn-submit",
        "[data-action='submit']",
    ]
    for selector in submit_selectors:
        try:
            btn = frame.locator(selector)
            if await btn.count() > 0:
                first = btn.first
                if await first.is_visible():
                    await first.click()
                    print(f"[solver] Submitted via: {selector}")
                    return
        except Exception:
            continue
    print("[solver] No submit button found — quiz may auto-advance.")
