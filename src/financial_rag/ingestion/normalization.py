"""Conservative text normalization that preserves financial document structure."""


def normalize_document_text(text: str) -> str:
    """Normalize line endings and excess blank lines without flattening structure.

    Internal spaces, Markdown headings, indentation, and pipe-delimited table rows
    are intentionally preserved. This is more conservative than the thesis
    notebook's global whitespace collapse.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ").replace("\f", "\n")

    lines: list[str] = []
    consecutive_blank_lines = 0
    for raw_line in normalized.split("\n"):
        line = raw_line.rstrip(" \t")
        if line:
            consecutive_blank_lines = 0
            lines.append(line)
            continue

        consecutive_blank_lines += 1
        if consecutive_blank_lines <= 1:
            lines.append("")

    return "\n".join(lines).strip("\n")
