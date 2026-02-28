"""Extract question text and answer options from a quiz frame via JS injection."""

from __future__ import annotations

from playwright.async_api import Frame

_EXTRACT_JS = """
() => {
    // ---- Find question text ----
    const questionSelectors = [
        '.question-text', '.h5p-question-content', '.quiz-question-text',
        '.question h2', '.question h3', '.question p',
        'legend', '[role="heading"]', 'h2', 'h3', 'p.question',
        '.question-stem', '.stem',
    ];
    let questionText = '';
    for (const sel of questionSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            const text = el.textContent.trim();
            if (text.length > 10) {
                questionText = text;
                break;
            }
        }
    }
    // Fallback: find the first paragraph-like element above the inputs
    if (!questionText) {
        const inputs = document.querySelectorAll(
            "input[type='radio'], input[type='checkbox']"
        );
        if (inputs.length > 0) {
            let el = inputs[0].parentElement;
            while (el) {
                const prev = el.previousElementSibling;
                if (prev && prev.textContent.trim().length > 10) {
                    questionText = prev.textContent.trim();
                    break;
                }
                el = el.parentElement;
            }
        }
    }

    // ---- Find answer options ----
    const options = [];

    // Standard radio/checkbox inputs
    const inputs = Array.from(document.querySelectorAll(
        "input[type='radio'], input[type='checkbox']"
    ));
    for (const input of inputs) {
        let labelText = '';
        // Try explicit label by 'for' attribute
        if (input.id) {
            const lbl = document.querySelector('label[for="' + input.id + '"]');
            if (lbl) labelText = lbl.textContent.trim();
        }
        // Try ancestor label
        if (!labelText) {
            const anc = input.closest('label');
            if (anc) labelText = anc.textContent.trim();
        }
        // Fall back to value or next sibling text
        if (!labelText) labelText = input.value || '';

        options.push({
            id: input.id || '',
            name: input.name || '',
            value: input.value || '',
            inputType: input.type,
            label: labelText,
            elementType: 'input',
        });
    }

    // ARIA-based options (when no standard inputs are found)
    if (options.length === 0) {
        const ariaOptions = Array.from(document.querySelectorAll(
            '[role="radio"], [role="option"], [role="checkbox"]'
        ));
        for (const el of ariaOptions) {
            options.push({
                id: el.id || '',
                name: '',
                value: el.getAttribute('data-value') || el.textContent.trim(),
                inputType: 'aria',
                label: el.textContent.trim(),
                elementType: 'aria',
            });
        }
    }

    // Button-list options (some custom LMS platforms use <li data-answer>)
    if (options.length === 0) {
        const btnOptions = Array.from(document.querySelectorAll(
            'li[data-answer], button[data-answer]'
        ));
        for (const el of btnOptions) {
            options.push({
                id: el.id || '',
                name: '',
                value: el.getAttribute('data-answer') || el.textContent.trim(),
                inputType: 'button',
                label: el.textContent.trim(),
                elementType: 'button',
            });
        }
    }

    return { questionText, options };
}
"""


async def extract_quiz(frame: Frame) -> dict:
    """
    Return { questionText: str, options: list[dict] } from the given frame.
    Each option dict has: id, name, value, inputType, label, elementType.
    """
    try:
        return await frame.evaluate(_EXTRACT_JS)
    except Exception as e:
        return {"questionText": "", "options": [], "error": str(e)}
