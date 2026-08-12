"""Pure Markdown heading extraction helpers."""

import re

MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$", re.MULTILINE)


def extract_section_heading(text: str) -> str | None:
    """Return the first ATX-style Markdown heading, without its hash prefix."""
    match = MARKDOWN_HEADING_PATTERN.search(text)
    return match.group(2).strip() if match else None


def section_heading_at(
    text: str,
    char_offset: int,
    *,
    default: str | None = None,
) -> str | None:
    """Return the nearest Markdown heading at or before a character offset."""
    heading = default
    for match in MARKDOWN_HEADING_PATTERN.finditer(text):
        if match.start() > char_offset:
            break
        heading = match.group(2).strip()
    return heading
