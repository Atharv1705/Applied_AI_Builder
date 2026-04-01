from __future__ import annotations


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """
    Split long text into overlapping chunks by character count.
    Preserves page markers when possible by snapping to newline boundaries near limits.
    """
    text = (text or "").strip()
    if not text:
        return []
    if max_chars <= 0:
        return [text]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            search = text.rfind("\n\n", start + max_chars // 2, end)
            if search > start:
                end = search
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(start + 1, end - overlap)
    return chunks
