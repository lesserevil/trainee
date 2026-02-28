"""Prompt templates for the vision-language model."""

FRAME_DESCRIPTION_PROMPT = (
    "This is a screenshot from an online training course.\n"
    "Context captured so far:\n{context}\n\n"
    "Describe the new information visible in this screenshot. "
    "Focus on: definitions, processes, rules, numbers, names, and key concepts. "
    "Be precise and concise. Do not repeat facts already in the context above."
)

QUIZ_ANSWER_PROMPT = (
    "You are a student answering a quiz at the end of a training course you just completed.\n\n"
    "COURSE KNOWLEDGE BASE:\n{context}\n\n"
    "QUIZ QUESTION:\n{question}\n\n"
    "ANSWER OPTIONS:\n{options}\n\n"
    "Instructions:\n"
    "- Select the correct answer(s) based ONLY on the course content above.\n"
    "- Do not use outside knowledge — only what the course taught.\n"
    "- For single-answer questions, reply with a single letter, e.g. B\n"
    "- For multiple-select questions, reply with a comma-separated list, e.g. A, C\n"
    "- Reply with the letter(s) only. No explanation."
)

FREE_TEXT_ANSWER_PROMPT = (
    "You are a student answering a quiz at the end of a training course you just completed.\n\n"
    "COURSE KNOWLEDGE BASE:\n{context}\n\n"
    "QUIZ QUESTION:\n{question}\n\n"
    "Instructions:\n"
    "- Answer the question in one short sentence or phrase based ONLY on the course content above.\n"
    "- Do not use outside knowledge — only what the course taught.\n"
    "- Do not explain your reasoning. Do not write a full paragraph.\n"
    "- Reply with your answer only. No preamble, no trailing punctuation unless it is part of the answer."
)

CONTEXT_COMPRESSION_PROMPT = (
    "Compress the following course notes into a concise, factual knowledge base "
    "that could be used to answer quiz questions.\n"
    "Preserve: key terms, definitions, processes, important numbers/dates, rules, "
    "and relationships. Remove redundancy. Use bullet points.\n\n"
    "EXISTING SUMMARY:\n{existing}\n\n"
    "NEW CONTENT TO INCORPORATE:\n{new_content}"
)
