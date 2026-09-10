"""Lifting fragile strings out of a prompt so a model cannot mistype them."""

from __future__ import annotations

import pytest

from phoenix_patchbay.handoff.literals import protect, restore

# The string that was actually corrupted in production: one alif short turned a
# 200 into a 404 in a handoff someone would later trust.
SLUG = "علاج-تساقط-الشعر-لدى-النساء"
AR_URL = f"https://salampolyclinic.om/ar/{SLUG}/"
CLINIC = "مجمع سلام الدولي"
ADDRESS = "بلوك 221، طريق 102"


def round_trip(text: str) -> str:
    (protected,), table = protect(text)
    restored, unknown = restore(protected, table)
    assert not unknown
    return restored


class TestWhatGetsProtected:
    def test_a_url_with_non_latin_in_it_is_taken_whole(self) -> None:
        (protected,), table = protect(f"see {AR_URL} now")

        assert AR_URL not in protected, "the model would have had to retype it"
        assert list(table.values()) == [AR_URL], "the URL was split into pieces"

    def test_an_arabic_phrase_keeps_its_spaces(self) -> None:
        (protected,), table = protect(f"shows {CLINIC} in the header")

        assert CLINIC in table.values()
        assert "in the header" in protected, "English around it was swallowed"

    def test_an_address_keeps_its_numbers(self) -> None:
        """Splitting on the digits leaves them loose for the model to move."""
        (_,), table = protect(f"address {ADDRESS} and more")

        assert ADDRESS in table.values()

    def test_ascii_identifiers_are_left_alone(self) -> None:
        """Paths and shas have been reproduced accurately; freezing them would
        stop the model rewording sentences that mention them."""
        text = "fixed custom/mu-plugins/verify-logic.php at commit f545f15"
        (protected,), table = protect(text)

        assert protected == text
        assert table == {}

    def test_the_same_literal_gets_one_placeholder_across_both_texts(self) -> None:
        """The old handoff and the new material usually name the same URL."""
        (a, b), table = protect(f"old: {AR_URL}", f"new: {AR_URL}")

        assert a.split(": ")[1] == b.split(": ")[1]
        assert len(table) == 1


class TestRoundTrip:
    @pytest.mark.parametrize(
        "text",
        [
            f"The page {AR_URL} returns 200",
            f"{ADDRESS}، مدينة السلطان قابوس then English",
            f"shows {CLINIC} in block مستعدة لمعرفة السبب الحقيقي؟ ok",
            "plain ascii only, nothing to protect",
            "",
            "price 35 OMR for الشعر service",
        ],
    )
    def test_text_survives_unchanged(self, text: str) -> None:
        assert round_trip(text) == text

    def test_the_exact_production_corruption_cannot_happen(self) -> None:
        """`لدى-النساء` became `لدى-لنساء`. The model never sees either now."""
        material = f"Arabic URL {AR_URL} now shows {CLINIC}."
        (protected,), table = protect(material)

        # Whatever the model does to the text it sees, it cannot damage a string
        # that is not in it.
        assert SLUG not in protected
        assert CLINIC not in protected

        mangled_by_model = protected.replace("now shows", "displays")
        restored, unknown = restore(mangled_by_model, table)

        assert AR_URL in restored
        assert CLINIC in restored
        assert not unknown


class TestSafety:
    def test_a_placeholder_the_model_invented_is_left_visible(self) -> None:
        """Deleting it would leave a sentence that reads fine and says nothing."""
        restored, unknown = restore("see [[L9]] there", {"[[L1]]": "x"})

        assert "[[L9]]" in restored
        assert unknown == ["[[L9]]"]

    def test_material_that_already_looks_like_a_placeholder_does_not_collide(
        self,
    ) -> None:
        """Substituting the wrong string back is worse than the corruption this
        exists to prevent."""
        text = f"the docs literally say [[L1]] and also {CLINIC}"
        (protected,), _table = protect(text)

        assert "[[LL1]]" in protected, "prefix did not escalate past the collision"
        assert round_trip(text) == text

    def test_restoring_without_a_table_changes_nothing(self) -> None:
        assert restore("plain text", {}) == ("plain text", [])
