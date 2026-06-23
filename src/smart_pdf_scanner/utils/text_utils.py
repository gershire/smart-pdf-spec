"""Text cleaning, normalisation, similarity, and reading-order utilities.

Provides pure-Python helpers for processing text extracted from PDF elements.
Designed to support the Structure Recognition stage (Requirement 5): heading
detection, duplicate/fuzzy matching between TOC entries and section headings,
and heuristic reading-order tie-breaking.

All functions rely only on the standard library (``re``, ``unicodedata``,
``difflib``) to keep the module lightweight and dependency-free.

References
----------
- Requirement 5: Structure Recognition
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "clean_text",
    "normalize_whitespace",
    "normalize_unicode",
    "strip_punctuation",
    "is_empty_or_whitespace",
    "truncate",
    "similarity_score",
    "is_similar",
    "best_match",
    "looks_like_heading",
    "extract_heading_number",
    "remove_heading_number",
    "words",
    "sentence_count",
    "is_likely_page_number",
    "merge_hyphenated",
]


# ---------------------------------------------------------------------------
# Basic cleaning
# ---------------------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace (including non-breaking spaces and tabs) to a single space.

    Args:
        text: Input string.

    Returns:
        String with all internal whitespace collapsed to ``' '`` and
        leading/trailing whitespace stripped.
    """
    return re.sub(r"[\s   　]+", " ", text).strip()


def normalize_unicode(text: str) -> str:
    """Apply NFC Unicode normalisation.

    Combines decomposed characters (e.g. ``e`` + combining accent) into their
    precomposed form so that string comparisons work as expected.

    Args:
        text: Input string.

    Returns:
        NFC-normalised string.
    """
    return unicodedata.normalize("NFC", text)


def strip_punctuation(text: str, *, keep: str = "") -> str:
    """Remove Unicode punctuation characters from ``text``.

    Args:
        text: Input string.
        keep: A string of punctuation characters to preserve (e.g. ``".,"``).

    Returns:
        String with punctuation removed (or kept if in ``keep``).
    """
    result = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("P") and ch not in keep:
            continue
        result.append(ch)
    return "".join(result)


def clean_text(text: str) -> str:
    """Apply a standard cleaning pipeline: normalise Unicode, collapse whitespace.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned string suitable for downstream processing.
    """
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    return text


def is_empty_or_whitespace(text: str) -> bool:
    """Return ``True`` if ``text`` is empty or contains only whitespace.

    Args:
        text: Input string.
    """
    return not text or not text.strip()


def truncate(text: str, max_length: int, *, suffix: str = "…") -> str:
    """Truncate ``text`` to at most ``max_length`` characters.

    Args:
        text: Input string.
        max_length: Maximum number of characters in the output.
        suffix: Appended to the truncated text to indicate omission.

    Returns:
        The original string (unchanged) if it fits, otherwise a truncated
        version ending with ``suffix``.
    """
    if len(text) <= max_length:
        return text
    cut = max_length - len(suffix)
    if cut <= 0:
        return suffix[:max_length]
    return text[:cut] + suffix


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------


def similarity_score(a: str, b: str, *, ignore_case: bool = True) -> float:
    """Return a similarity ratio in ``[0.0, 1.0]`` between two strings.

    Uses :class:`difflib.SequenceMatcher` (Ratcliff/Obershelp algorithm).

    Args:
        a: First string.
        b: Second string.
        ignore_case: Normalise both strings to lower-case before comparison.

    Returns:
        Similarity ratio where ``1.0`` means identical.
    """
    if ignore_case:
        a, b = a.casefold(), b.casefold()
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def is_similar(a: str, b: str, *, threshold: float = 0.85, ignore_case: bool = True) -> bool:
    """Return ``True`` if two strings are similar above ``threshold``.

    Args:
        a: First string.
        b: Second string.
        threshold: Minimum :func:`similarity_score` required.
        ignore_case: Passed to :func:`similarity_score`.
    """
    return similarity_score(a, b, ignore_case=ignore_case) >= threshold


def best_match(
    query: str,
    candidates: Sequence[str],
    *,
    threshold: float = 0.0,
    ignore_case: bool = True,
) -> Optional[Tuple[int, str, float]]:
    """Find the best-matching string in ``candidates`` for ``query``.

    Args:
        query: The string to look up.
        candidates: Strings to search.
        threshold: Minimum score required to return a result. Pass ``0.0``
            (default) to always return the best match regardless of quality.
        ignore_case: Passed to :func:`similarity_score`.

    Returns:
        A ``(index, candidate, score)`` triple for the best match, or ``None``
        when ``candidates`` is empty or no match meets ``threshold``.
    """
    best_idx: Optional[int] = None
    best_score = -1.0
    for idx, candidate in enumerate(candidates):
        score = similarity_score(query, candidate, ignore_case=ignore_case)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is None or best_score < threshold:
        return None
    return (best_idx, candidates[best_idx], best_score)


# ---------------------------------------------------------------------------
# Heading heuristics
# ---------------------------------------------------------------------------

# Matches common heading number prefixes: "1.", "1.2", "1.2.3.", "A.", "I.V."
_HEADING_NUMBER_RE = re.compile(
    r"^(?:"
    r"[0-9]+(?:\.[0-9]+)*\.?"   # numeric: 1 / 1.2 / 1.2.3.
    r"|[A-Z](?:\.[A-Z])*\.?"    # alphabetic: A / A.B
    r"|[IVXLCDM]+\.?"           # Roman numerals
    r")\s+"
)


def looks_like_heading(
    text: str,
    *,
    max_words: int = 12,
    min_chars: int = 2,
) -> bool:
    """Heuristically decide whether ``text`` looks like a section heading.

    The heuristic checks that the text:
    - is non-empty and meets ``min_chars``,
    - contains no more than ``max_words`` (headings are typically short),
    - does not end with a full stop (prose sentences usually do),
    - starts with a capital letter or a heading number prefix.

    Args:
        text: Cleaned extracted text.
        max_words: Maximum number of space-separated tokens to consider a
            heading. Long runs of text are very unlikely to be headings.
        min_chars: Minimum character count (after stripping) to be a heading.

    Returns:
        ``True`` if the text passes the heading heuristic.
    """
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    word_list = stripped.split()
    if len(word_list) > max_words:
        return False
    # Headings rarely end with a period (unless it's a numbered heading).
    if stripped.endswith(".") and not _HEADING_NUMBER_RE.match(stripped):
        return False
    first_char = stripped[0]
    return first_char.isupper() or first_char.isdigit()


def extract_heading_number(text: str) -> Optional[str]:
    """Extract a leading numbering prefix from a heading string.

    Args:
        text: Heading text (may or may not have a number prefix).

    Returns:
        The numbering prefix (e.g. ``"1.2."``), or ``None`` if absent.
    """
    m = _HEADING_NUMBER_RE.match(text.strip())
    return m.group(0).rstrip() if m else None


def remove_heading_number(text: str) -> str:
    """Strip the leading numbering prefix from a heading string.

    Args:
        text: Heading text.

    Returns:
        Heading text without the leading number (stripped).
    """
    stripped = text.strip()
    m = _HEADING_NUMBER_RE.match(stripped)
    if m:
        return stripped[m.end():].strip()
    return stripped


# ---------------------------------------------------------------------------
# Miscellaneous helpers
# ---------------------------------------------------------------------------


def words(text: str) -> List[str]:
    """Split ``text`` into a list of non-empty word tokens.

    Splits on whitespace and returns only non-empty tokens.

    Args:
        text: Input string.

    Returns:
        List of word tokens.
    """
    return [w for w in text.split() if w]


def sentence_count(text: str) -> int:
    """Estimate the number of sentences in ``text``.

    Uses a simple rule: splits on ``. ``, ``! ``, and ``? `` followed by a
    capital letter or end-of-string. Not intended as a precise NLP tokeniser;
    good enough for deciding whether a text block is prose or a heading.

    Args:
        text: Input string.

    Returns:
        Estimated sentence count (at least 1 for non-empty text).
    """
    stripped = text.strip()
    if not stripped:
        return 0
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", stripped)
    return len(sentences)


def is_likely_page_number(text: str) -> bool:
    """Return ``True`` if ``text`` looks like a standalone page number.

    Matches strings like ``"42"``, ``"- 3 -"``, ``"Page 5"``, ``"p. 12"``.

    Args:
        text: Cleaned extracted text.
    """
    stripped = text.strip()
    patterns = [
        r"^\d+$",                       # bare number
        r"^-\s*\d+\s*-$",              # "- 42 -"
        r"^[Pp](?:age|\.)\s*\d+$",     # "Page 5" / "p. 5"
    ]
    return any(re.match(p, stripped) for p in patterns)


def merge_hyphenated(lines: Iterable[str]) -> str:
    """Join lines, merging words that were hyphenated across a line break.

    PDF text extraction sometimes splits a word with a soft hyphen at the end
    of a line. This function detects trailing hyphens and rejoins the word.

    Args:
        lines: Sequence of extracted text lines.

    Returns:
        Single string with hyphenated line-breaks resolved.
    """
    result: List[str] = []
    for line in lines:
        stripped = line.rstrip()
        if result and result[-1].endswith("-"):
            # Merge: remove the trailing hyphen and attach next line without space.
            result[-1] = result[-1][:-1] + stripped.lstrip()
        else:
            if result:
                result.append(" ")
            result.append(stripped)
    return "".join(result)
