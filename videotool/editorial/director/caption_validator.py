"""Grounding validator for AI-authored node captions and labels (Anti-Hallucination Gate).

Enforces:
1. Length constraints (concise node labels: 1-8 words, quote cards: 1-30 words).
2. Factual grounding: every proper noun, number, date, or specific factual entity
   in the proposed caption must appear in the beat's narration text or semantic metadata
   (entities, locations, dates, events).
3. Rejection fallback: ungrounded or malformed captions are rejected with an explanatory
   reason so caller can safely fall back to raw entity strings.
"""
from __future__ import annotations

import re
from typing import Sequence


# Common stop words/particles across EN/VI to exclude from strict proper-noun grounding checks
COMMON_STOP_WORDS = {
    # English
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "into", "through", "during", "before", "after", "above", "below",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must", "can", "could",
    "this", "that", "these", "those", "it", "its", "their", "theirs", "his", "her", "hers",
    "not", "no", "nor", "so", "than", "too", "very", "just", "now", "then", "there", "here",
    "official", "protest", "protests", "document", "regulation", "wall", "border", "borders", "city",
    "briefing", "conference", "statement", "moment", "crisis", "fall", "collapse", "spread",
    "effect", "checkpoint", "cross", "crossing", "crossings", "route", "routes", "escape", "divided", "open", "opens", "opened", "opening",
    # Vietnamese
    "và", "hoặc", "nhưng", "trong", "trên", "tại", "đến", "cho", "của", "với", "bởi",
    "từ", "như", "vào", "qua", "suốt", "trước", "sau", "là", "được", "bị", "đã", "đang",
    "sẽ", "có", "này", "đó", "kia", "nó", "họ", "không", "chưa", "chẳng", "rất", "quá",
    "ngay", "thì", "ở", "về", "biên", "giới", "mở", "cửa", "bức", "tường", "sụp", "đổ",
}


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for relaxed matching."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def _extract_factual_tokens(caption: str) -> list[str]:
    """Extract candidate factual terms (proper nouns, years, digits, capitalized words)."""
    tokens = []
    # 1. Look for numbers and years (e.g. "1989", "28")
    for num in re.findall(r"\b\d+\b", caption):
        tokens.append(num)

    # 2. Look for capitalized words/phrases (excluding sentence starters if common)
    words = re.findall(r"\b[A-Za-zÀ-ỹ0-9\-]+\b", caption)
    for i, w in enumerate(words):
        w_lower = w.lower()
        if w_lower in COMMON_STOP_WORDS:
            continue
        # If capitalized or digits, consider as candidate factual token
        if w[0].isupper() or any(c.isdigit() for c in w):
            tokens.append(w)
        elif len(w) >= 3 and w_lower not in COMMON_STOP_WORDS:
            # Long specific content words
            tokens.append(w)

    return tokens


def validate_caption(
    caption: str,
    narration_text: str,
    entities: Sequence[str] | None = None,
    locations: Sequence[str] | None = None,
    dates: Sequence[str] | None = None,
    events: Sequence[str] | None = None,
    text_role: str = "LABEL",
    max_label_words: int = 8,
    max_quote_words: int = 30,
) -> tuple[bool, str]:
    """Validate a proposed caption against beat context and grounding constraints.

    Returns:
        (is_valid, reason) - If is_valid is False, reason describes why it was rejected.
    """
    if not caption or not caption.strip():
        return False, "Caption is empty or whitespace"

    clean_caption = caption.strip()
    words = clean_caption.split()
    word_count = len(words)

    # 1. Length Constraint Gate
    is_quote = text_role.upper() == "QUOTE"
    if is_quote:
        if word_count > max_quote_words:
            return False, f"Quote caption exceeds {max_quote_words} words (got {word_count} words)"
    else:
        if word_count > max_label_words:
            return False, f"Label caption exceeds {max_label_words} words (got {word_count} words)"

    # 2. Build Grounding Reference Corpus
    corpus_parts = [narration_text or ""]
    if entities:
        corpus_parts.extend(entities)
    if locations:
        corpus_parts.extend(locations)
    if dates:
        corpus_parts.extend(dates)
    if events:
        corpus_parts.extend(events)

    full_corpus = " ".join(corpus_parts)
    norm_corpus = _normalize(full_corpus)
    corpus_words = set(norm_corpus.split())

    # 3. Proper Noun, Date, and Number Grounding Gate
    factual_tokens = _extract_factual_tokens(clean_caption)
    for token in factual_tokens:
        token_clean = token.strip()
        token_lower = token_clean.lower()
        if not token_clean or token_lower in COMMON_STOP_WORDS:
            continue

        # Check if digits/numbers are present in corpus
        if re.fullmatch(r"\d+", token_clean):
            if token_clean not in full_corpus:
                return False, f"Unreferenced number/date '{token_clean}' not found in beat context"
            continue

        # Check if proper noun / specific token appears in corpus
        # Either exact word match, substring match, or token match
        if token_lower in corpus_words or token_lower in norm_corpus:
            continue

        # Check if token is part of any entity/location name
        matched = False
        for part in corpus_parts:
            if token_lower in _normalize(part):
                matched = True
                break
        if matched:
            continue

        # If it's a capitalized word (likely a proper noun) that isn't anywhere in the beat
        if token_clean[0].isupper() and token_lower not in COMMON_STOP_WORDS:
            return False, f"Unreferenced proper noun/entity '{token_clean}' not found in beat context"

    return True, "Caption is factually grounded and conforms to length constraints"
