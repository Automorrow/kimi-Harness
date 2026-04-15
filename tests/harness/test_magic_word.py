"""Unit tests for kimi_cli.harness.magic_word."""

from __future__ import annotations

from kimi_cli.harness.magic_word import MagicWordResult, detect_magic_word


class TestNoDetection:
    """detect_magic_word returns detected=False for normal input."""

    def test_plain_english(self) -> None:
        r = detect_magic_word("fix this bug")
        assert r.detected is False
        assert r.cleaned_input == "fix this bug"

    def test_plain_chinese(self) -> None:
        r = detect_magic_word("帮我审查代码")
        assert r.detected is False
        assert r.cleaned_input == "帮我审查代码"

    def test_empty_string(self) -> None:
        r = detect_magic_word("")
        assert r.detected is False
        assert r.cleaned_input == ""

    def test_word_boundary_harnessing(self) -> None:
        """'harnessing' should NOT match."""
        r = detect_magic_word("harnessing the power")
        assert r.detected is False
        assert r.cleaned_input == "harnessing the power"

    def test_word_boundary_unharness(self) -> None:
        """'unharness' should NOT match."""
        r = detect_magic_word("unharness the dog")
        assert r.detected is False
        assert r.cleaned_input == "unharness the dog"

    def test_word_boundary_hns123(self) -> None:
        """'hns123' should NOT match."""
        r = detect_magic_word("hns123 is not a magic word")
        assert r.detected is False
        assert r.cleaned_input == "hns123 is not a magic word"

    def test_substring_within_word(self) -> None:
        """'aharnessb' should NOT match (not word boundary)."""
        r = detect_magic_word("aharnessb")
        assert r.detected is False


class TestHarnessDetection:
    """detect_magic_word detects 'harness' at various positions."""

    def test_beginning(self) -> None:
        r = detect_magic_word("harness fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_middle(self) -> None:
        r = detect_magic_word("please harness fix this")
        assert r.detected is True
        assert r.cleaned_input == "please fix this"

    def test_end(self) -> None:
        r = detect_magic_word("fix this harness")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_uppercase(self) -> None:
        r = detect_magic_word("HARNESS fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_mixed_case(self) -> None:
        r = detect_magic_word("hArNeSs fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_title_case(self) -> None:
        r = detect_magic_word("Harness fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_only_magic_word(self) -> None:
        """Input is just 'harness' -> cleaned_input should be empty."""
        r = detect_magic_word("harness")
        assert r.detected is True
        assert r.cleaned_input == ""

    def test_with_chinese(self) -> None:
        r = detect_magic_word("harness 帮我审查代码")
        assert r.detected is True
        assert r.cleaned_input == "帮我审查代码"


class TestHnsDetection:
    """detect_magic_word detects 'hns' at various positions."""

    def test_beginning(self) -> None:
        r = detect_magic_word("hns fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_middle(self) -> None:
        r = detect_magic_word("please hns fix this")
        assert r.detected is True
        assert r.cleaned_input == "please fix this"

    def test_end(self) -> None:
        r = detect_magic_word("fix this hns")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_uppercase(self) -> None:
        r = detect_magic_word("HNS fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_mixed_case(self) -> None:
        r = detect_magic_word("HnS fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_only_magic_word(self) -> None:
        r = detect_magic_word("hns")
        assert r.detected is True
        assert r.cleaned_input == ""


class TestMultipleMagicWords:
    """Multiple magic words in one input."""

    def test_harness_and_hns(self) -> None:
        r = detect_magic_word("harness hns do it")
        assert r.detected is True
        assert r.cleaned_input == "do it"

    def test_repeated_harness(self) -> None:
        r = detect_magic_word("harness harness fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"


class TestCleaning:
    """Cleaned input has proper whitespace and punctuation handling."""

    def test_trailing_comma(self) -> None:
        r = detect_magic_word("harness, fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_leading_semicolon(self) -> None:
        r = detect_magic_word("harness ; fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_surrounding_punctuation(self) -> None:
        r = detect_magic_word("harness , ; fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_colon_after(self) -> None:
        r = detect_magic_word("harness: fix this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"

    def test_multiple_spaces_collapsed(self) -> None:
        r = detect_magic_word("harness    fix    this")
        assert r.detected is True
        assert r.cleaned_input == "fix this"


class TestResultFields:
    """MagicWordResult fields are correct when detected."""

    def test_default_values(self) -> None:
        r = detect_magic_word("harness do something")
        assert isinstance(r, MagicWordResult)
        assert r.detected is True
        assert r.permission_mode == "plan"
        assert r.memory == "global"
        assert r.isolation == "command"

    def test_frozen(self) -> None:
        """MagicWordResult should be immutable (frozen=True)."""
        r = detect_magic_word("harness")
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            r.detected = False  # type: ignore[misc]


# Need pytest for frozen dataclass test
import pytest  # noqa: E402
