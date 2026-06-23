"""Unit tests for :mod:`smart_pdf_scanner.utils.text_utils`."""

import pytest

from smart_pdf_scanner.utils import text_utils as tu


# ---------------------------------------------------------------------------
# normalize_whitespace
# ---------------------------------------------------------------------------

class TestNormalizeWhitespace:
    def test_collapses_internal_spaces(self):
        assert tu.normalize_whitespace("a  b   c") == "a b c"

    def test_collapses_tabs(self):
        assert tu.normalize_whitespace("a\t\tb") == "a b"

    def test_collapses_newlines(self):
        assert tu.normalize_whitespace("a\n b") == "a b"

    def test_strips_leading_trailing(self):
        assert tu.normalize_whitespace("  hello  ") == "hello"

    def test_non_breaking_space(self):
        assert tu.normalize_whitespace("a b") == "a b"

    def test_empty_string(self):
        assert tu.normalize_whitespace("") == ""

    def test_already_normalised(self):
        assert tu.normalize_whitespace("hello world") == "hello world"


# ---------------------------------------------------------------------------
# normalize_unicode
# ---------------------------------------------------------------------------

class TestNormalizeUnicode:
    def test_nfc_combines_decomposed(self):
        # "e" + combining acute accent → é (NFC)
        decomposed = "é"
        composed = tu.normalize_unicode(decomposed)
        assert composed == "\xe9"
        assert len(composed) == 1

    def test_already_nfc_unchanged(self):
        assert tu.normalize_unicode("hello") == "hello"


# ---------------------------------------------------------------------------
# strip_punctuation
# ---------------------------------------------------------------------------

class TestStripPunctuation:
    def test_removes_common_punctuation(self):
        assert tu.strip_punctuation("Hello, world!") == "Hello world"

    def test_keep_preserves_chars(self):
        result = tu.strip_punctuation("Hello, world!", keep=",")
        assert result == "Hello, world"

    def test_empty_string(self):
        assert tu.strip_punctuation("") == ""

    def test_no_punctuation_unchanged(self):
        assert tu.strip_punctuation("Hello world") == "Hello world"


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_combines_unicode_and_whitespace_normalisation(self):
        text = "é  hello  "
        result = tu.clean_text(text)
        assert result == "\xe9 hello"

    def test_empty(self):
        assert tu.clean_text("") == ""


# ---------------------------------------------------------------------------
# is_empty_or_whitespace
# ---------------------------------------------------------------------------

class TestIsEmptyOrWhitespace:
    def test_empty_string(self):
        assert tu.is_empty_or_whitespace("") is True

    def test_whitespace_only(self):
        assert tu.is_empty_or_whitespace("   \t\n") is True

    def test_non_empty(self):
        assert tu.is_empty_or_whitespace("hello") is False

    def test_single_char(self):
        assert tu.is_empty_or_whitespace("a") is False


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text_unchanged(self):
        assert tu.truncate("hi", 10) == "hi"

    def test_exact_length_unchanged(self):
        assert tu.truncate("hello", 5) == "hello"

    def test_truncates_with_suffix(self):
        result = tu.truncate("hello world", 8)
        assert result == "hello w…"
        assert len(result) == 8

    def test_custom_suffix(self):
        result = tu.truncate("hello world", 8, suffix="...")
        assert result == "hello..."
        assert len(result) == 8

    def test_max_length_smaller_than_suffix(self):
        result = tu.truncate("hello", 1, suffix="…")
        assert len(result) <= 1

    def test_max_length_zero(self):
        result = tu.truncate("hello", 0, suffix="…")
        assert result == "…"[:0]


# ---------------------------------------------------------------------------
# similarity_score
# ---------------------------------------------------------------------------

class TestSimilarityScore:
    def test_identical_strings(self):
        assert tu.similarity_score("hello", "hello") == 1.0

    def test_completely_different(self):
        assert tu.similarity_score("abc", "xyz") == 0.0

    def test_partial_similarity(self):
        score = tu.similarity_score("hello", "hello world")
        assert 0.0 < score < 1.0

    def test_case_insensitive_by_default(self):
        assert tu.similarity_score("Hello", "hello") == 1.0

    def test_case_sensitive_when_requested(self):
        assert tu.similarity_score("Hello", "hello", ignore_case=False) < 1.0

    def test_both_empty(self):
        assert tu.similarity_score("", "") == 1.0


# ---------------------------------------------------------------------------
# is_similar
# ---------------------------------------------------------------------------

class TestIsSimilar:
    def test_identical(self):
        assert tu.is_similar("abc", "abc") is True

    def test_above_default_threshold(self):
        assert tu.is_similar("Introduction", "Introduction") is True

    def test_below_threshold(self):
        assert tu.is_similar("abc", "xyz", threshold=0.9) is False

    def test_custom_low_threshold(self):
        assert tu.is_similar("abc", "abz", threshold=0.5) is True


# ---------------------------------------------------------------------------
# best_match
# ---------------------------------------------------------------------------

class TestBestMatch:
    def test_returns_best_candidate(self):
        result = tu.best_match("hello", ["world", "hello there", "hello"])
        assert result is not None
        idx, candidate, score = result
        assert candidate == "hello"
        assert score == 1.0

    def test_empty_candidates_returns_none(self):
        assert tu.best_match("hello", []) is None

    def test_threshold_not_met_returns_none(self):
        result = tu.best_match("hello", ["xyz", "abc"], threshold=0.9)
        assert result is None

    def test_returns_index_of_best(self):
        result = tu.best_match("cat", ["dog", "cat", "bird"])
        assert result is not None
        assert result[0] == 1

    def test_zero_threshold_always_returns(self):
        result = tu.best_match("hello", ["xyz"], threshold=0.0)
        assert result is not None


# ---------------------------------------------------------------------------
# looks_like_heading
# ---------------------------------------------------------------------------

class TestLooksLikeHeading:
    def test_simple_heading(self):
        assert tu.looks_like_heading("Introduction") is True

    def test_numbered_heading(self):
        assert tu.looks_like_heading("1. Overview") is True

    def test_too_long(self):
        long_text = " ".join(["word"] * 15)
        assert tu.looks_like_heading(long_text) is False

    def test_ends_with_period(self):
        assert tu.looks_like_heading("This is a sentence.") is False

    def test_too_short(self):
        assert tu.looks_like_heading("A") is False

    def test_starts_with_lowercase(self):
        assert tu.looks_like_heading("introduction") is False

    def test_exactly_max_words(self):
        heading = " ".join(["Word"] * 12)
        assert tu.looks_like_heading(heading) is True

    def test_one_over_max_words(self):
        heading = " ".join(["Word"] * 13)
        assert tu.looks_like_heading(heading) is False

    def test_roman_numeral_heading(self):
        assert tu.looks_like_heading("IV. Results") is True


# ---------------------------------------------------------------------------
# extract_heading_number
# ---------------------------------------------------------------------------

class TestExtractHeadingNumber:
    def test_numeric_prefix(self):
        assert tu.extract_heading_number("1. Overview") == "1."

    def test_dotted_numeric_prefix(self):
        assert tu.extract_heading_number("1.2 Details") == "1.2"

    def test_no_prefix(self):
        assert tu.extract_heading_number("Overview") is None

    def test_alphabetic_prefix(self):
        assert tu.extract_heading_number("A. Appendix") == "A."

    def test_deep_nesting(self):
        result = tu.extract_heading_number("1.2.3. Section")
        assert result == "1.2.3."


# ---------------------------------------------------------------------------
# remove_heading_number
# ---------------------------------------------------------------------------

class TestRemoveHeadingNumber:
    def test_removes_numeric_prefix(self):
        assert tu.remove_heading_number("1. Overview") == "Overview"

    def test_removes_dotted_prefix(self):
        assert tu.remove_heading_number("2.3 Details") == "Details"

    def test_no_prefix_unchanged(self):
        assert tu.remove_heading_number("Overview") == "Overview"

    def test_strips_result(self):
        assert tu.remove_heading_number("  1. Overview  ") == "Overview"


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------

class TestWords:
    def test_basic(self):
        assert tu.words("hello world") == ["hello", "world"]

    def test_empty_string(self):
        assert tu.words("") == []

    def test_extra_whitespace(self):
        assert tu.words("  a  b  c  ") == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# sentence_count
# ---------------------------------------------------------------------------

class TestSentenceCount:
    def test_empty_string(self):
        assert tu.sentence_count("") == 0

    def test_single_sentence(self):
        assert tu.sentence_count("Hello world.") == 1

    def test_two_sentences(self):
        assert tu.sentence_count("Hello. World.") == 2

    def test_question_and_exclamation(self):
        assert tu.sentence_count("Really? Yes! Great.") == 3


# ---------------------------------------------------------------------------
# is_likely_page_number
# ---------------------------------------------------------------------------

class TestIsLikelyPageNumber:
    def test_bare_number(self):
        assert tu.is_likely_page_number("42") is True

    def test_decorated_number(self):
        assert tu.is_likely_page_number("- 3 -") is True

    def test_page_prefix(self):
        assert tu.is_likely_page_number("Page 5") is True

    def test_lowercase_p_prefix(self):
        assert tu.is_likely_page_number("p. 12") is True

    def test_regular_text(self):
        assert tu.is_likely_page_number("Introduction") is False

    def test_empty(self):
        assert tu.is_likely_page_number("") is False


# ---------------------------------------------------------------------------
# merge_hyphenated
# ---------------------------------------------------------------------------

class TestMergeHyphenated:
    def test_no_hyphens(self):
        result = tu.merge_hyphenated(["hello", "world"])
        assert result == "hello world"

    def test_merges_hyphenated_break(self):
        result = tu.merge_hyphenated(["con-", "nection"])
        assert result == "connection"

    def test_multiple_merges(self):
        result = tu.merge_hyphenated(["pre-", "pro-", "cessing"])
        assert result == "preprocessing"  # pre- + pro- + cessing

    def test_single_line(self):
        assert tu.merge_hyphenated(["hello"]) == "hello"

    def test_empty_iterable(self):
        assert tu.merge_hyphenated([]) == ""
