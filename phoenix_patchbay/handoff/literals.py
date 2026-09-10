"""Keeping exact strings exact when a model rewrites a document around them.

A write-up model has no reason to retype a URL, and every reason not to: it
retypes it from memory and occasionally drops a character. In production it
turned `…لدى-النساء` into `…لدى-لنساء` — one missing alif, a 404 instead of a
200, in a handoff someone would later trust.

Choosing a better model does not fix this, it only lowers the rate. So the
fragile strings never reach the model at all: they are lifted out, replaced
with plain ASCII placeholders, and put back verbatim afterwards. The model
arranges the document; it does not transcribe the literals.

What counts as fragile is deliberately narrow — URLs, and runs of non-ASCII
text. Those are the demonstrated risk. ASCII paths, commit shas and post ids
have been reproduced accurately throughout, and freezing them too would stop
the model rewording sentences that mention them.
"""

from __future__ import annotations

import re

#: A URL, up to the first character that cannot be part of one. Trailing
#: punctuation is excluded so "see https://x/y." keeps its full stop outside.
_URL = re.compile(r"https?://[^\s<>`\"']+[^\s<>`\"'.,;:!?)\]]")

#: A run of non-ASCII text: anchored on non-ASCII characters, allowed to span
#: the spaces and punctuation *between* them, and required to end on one. That
#: keeps "مجمع سلام الدولي" whole while stopping before the English that
#: follows it, so the model can still reword the sentence around it. Digits
#: count as connectors: "بلوك 221، طريق 102" is one address, and splitting it
#: around the numbers would leave those numbers loose for the model to move.
#: A run may also end on digits, so "\u0637\u0631\u064a\u0642 102" keeps its number.
_NON_ASCII = re.compile(
    # \u200e/\u200f are the LTR/RTL marks, written as escapes because they are
    # invisible in a source file; \u2013/\u2014 are the en and em dashes.
    r"[^\x00-\x7F]+"
    r"(?:[ \t\u200e\u200f.,\-\u2013\u2014_/\u060c\u061b:]+(?:[^\x00-\x7F]+|[0-9]+))*"
)

#: Placeholders are ASCII and boring on purpose: whatever mangles Arabic must
#: not also mangle these.
_TOKEN = re.compile(r"\[\[([A-Z]+\d+)\]\]")


def _prefix_for(*texts: str) -> str:
    """A placeholder prefix that does not already occur in the material.

    Transcripts contain arbitrary text, including, one day, something shaped
    like a placeholder. Colliding would substitute the wrong string back in,
    which is worse than the corruption this exists to prevent.
    """
    prefix = "L"
    while any(f"[[{prefix}" in t for t in texts):
        prefix += "L"
    return prefix


def protect(*texts: str) -> tuple[list[str], dict[str, str]]:
    """Replace fragile literals across *texts* with shared placeholders.

    One table across every text on purpose: the same URL usually appears in
    both the existing handoff and the new material, and giving it one
    placeholder means the model sees them as the same thing.
    """
    prefix = _prefix_for(*texts)
    table: dict[str, str] = {}
    seen: dict[str, str] = {}
    out: list[str] = []

    def swap(match: re.Match[str]) -> str:
        literal = match.group(0)
        if literal not in seen:
            token = f"[[{prefix}{len(seen) + 1}]]"
            seen[literal] = token
            table[token] = literal
        return seen[literal]

    for text in texts:
        # URLs first: a URL containing non-ASCII must be taken whole, not
        # shredded into an ASCII half and an Arabic half.
        swapped = _URL.sub(swap, text or "")
        swapped = _NON_ASCII.sub(swap, swapped)
        out.append(swapped)
    return out, table


def restore(text: str, table: dict[str, str]) -> tuple[str, list[str]]:
    """Put the literals back. Returns the text and any unknown placeholders.

    An unknown placeholder means the model invented one. It is left in place
    rather than deleted: a visible ``[[L9]]`` in the handoff is a defect
    someone will notice and report, while silently dropping it would leave a
    sentence that reads fine and says something false.
    """
    unknown: list[str] = []
    # Only tokens carrying this run's prefix are ours. Text that merely looks
    # like a placeholder — the material said "[[L1]]" before we touched it, and
    # the prefix escalated past it — belongs to the document and is not a
    # missing literal.
    ours = {re.sub(r"\d+", "", key.strip("[]")) for key in table}

    def put(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in table:
            return table[token]
        if re.sub(r"\d+", "", match.group(1)) in ours:
            unknown.append(token)
        return token

    return _TOKEN.sub(put, text or ""), unknown
