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

_EXTRACT_FREE_TEXT_JS = """
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
        const inputs = document.querySelectorAll("input[type='text'], textarea");
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

    // ---- Find text input fields ----
    const options = [];
    const inputSelectors = ["input[type='text']", "textarea"];
    for (const sel of inputSelectors) {
        const inputs = Array.from(document.querySelectorAll(sel));
        if (inputs.length === 0) continue;
        for (const input of inputs) {
            let label = '';
            if (input.id) {
                const lbl = document.querySelector('label[for="' + CSS.escape(input.id) + '"]');
                if (lbl) label = lbl.textContent.trim();
            }
            if (!label) {
                const anc = input.closest('label');
                if (anc) label = anc.textContent.trim();
            }
            if (!label && input.placeholder) label = input.placeholder;
            const selector = input.id ? '#' + CSS.escape(input.id) : sel;
            options.push({
                id: input.id || '',
                name: input.name || '',
                inputType: input.tagName.toLowerCase() === 'textarea' ? 'textarea' : 'text',
                selector: selector,
                label: label,
                elementType: 'free_text',
            });
        }
        break; // stop at first selector that yielded results
    }

    return { questionText, options, questionType: 'free_text' };
}
"""


async def extract_quiz(frame: Frame, question_type: str = "multiple_choice") -> dict:
    """
    Return { questionText: str, options: list[dict] } from the given frame.

    For multiple_choice: options are radio/checkbox/aria/button dicts.
    For free_text: options are text input dicts with inputType/selector/label/elementType.
    """
    try:
        if question_type == "free_text":
            return await frame.evaluate(_EXTRACT_FREE_TEXT_JS)
        return await frame.evaluate(_EXTRACT_JS)
    except Exception as e:
        return {"questionText": "", "options": [], "error": str(e)}
