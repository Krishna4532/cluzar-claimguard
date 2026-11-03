import re


def normalize_text(text: str) -> str:
    """
    Normalizes whitespace and formatting while preserving original semantic content.
    Rules:
    - Normalizes line endings to standard Unix newline ('\\n').
    - Removes trailing and leading spaces from individual lines.
    - Condenses sequences of 3 or more newlines into double newlines (paragraphs preserved).
    - Preserves all punctuation, digits, symbols (₹, $, %, etc.), dates, and product names.
    - Never modifies, translates, or romanizes Hindi or Hinglish text.
    """
    if not text:
        return ""

    # 1. Normalize line breaks (\r\n and \r -> \n)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip trailing/leading horizontal whitespace on each line
    lines = [re.sub(r"[ \t]+$", "", line) for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # 3. Collapse 3 or more consecutive newlines into 2 (paragraph boundary)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    # 4. Strip outer leading/trailing whitespace
    return normalized.strip()

