"""Japanese text chunking using sentence boundary detection."""
import re
import logging

logger = logging.getLogger(__name__)

SENTENCE_ENDINGS = re.compile(r"(?<=[。！？\n])")


def split_at_sentence_boundaries(text: str) -> list[str]:
    """Split text into sentences at Japanese sentence boundaries (。！？ and newlines)."""
    parts = SENTENCE_ENDINGS.split(text)
    return [p.strip() for p in parts if p.strip()]


def count_tokens_approximate(text: str) -> int:
    """Approximate token count. JP chars ~1.5 tokens each, ASCII words ~1 token."""
    jp_chars = sum(1 for c in text if ord(c) > 0x3000)
    ascii_words = len(re.findall(r"[a-zA-Z0-9]+", text))
    return int(jp_chars * 1.5 + ascii_words)


def split_into_chunks(
    text: str,
    max_tokens: int = 512,
    overlap_sentences: int = 1,
) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Short texts (< max_tokens) return as single-element list.
    Chunks overlap by overlap_sentences sentences for context continuity.
    """
    if count_tokens_approximate(text) <= max_tokens:
        return [text]

    sentences = split_at_sentence_boundaries(text)
    if not sentences:
        return [text]

    chunks = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens_approximate(sentence)
        if current_tokens + sentence_tokens > max_tokens and current_sentences:
            chunks.append("".join(current_sentences))
            if overlap_sentences > 0 and len(current_sentences) >= overlap_sentences:
                current_sentences = current_sentences[-overlap_sentences:]
                current_tokens = sum(count_tokens_approximate(s) for s in current_sentences)
            else:
                current_sentences = []
                current_tokens = 0
        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    if current_sentences:
        chunks.append("".join(current_sentences))

    return chunks if chunks else [text]
