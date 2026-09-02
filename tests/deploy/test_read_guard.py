"""The Read hook shipped in deploy/seed/hooks, exercised through node.

The hook is the only thing standing between a curious agent and a 600 KB file
in the transcript, so it is tested by running it, not by reading it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "deploy" / "seed" / "hooks" / "read-guard.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run_hook(file_path: str, *, tmpdir: Path, tool: str = "Read") -> dict:
    """Invoke the hook the way Claude Code does and return its JSON, if any."""
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})
    proc = subprocess.run(
        ["node", str(HOOK)],
        input=payload,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env={"TMPDIR": str(tmpdir), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def approve(name: str, tmpdir: Path) -> None:
    """Stand in for the user saying yes, the way the deny message describes."""
    approved = tmpdir / "agent-read-approved"
    approved.mkdir(parents=True, exist_ok=True)
    (approved / name).touch()


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    """A one-page PDF with a real text layer, written by hand.

    No library: the point is a file `pdftotext` will accept, and the bytes for
    that are short enough to spell out.
    """
    body = b"BT /F1 24 Tf 72 700 Td (Salam Polyclinic verification letter) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    path = tmp_path / "letter.pdf"
    path.write_bytes(bytes(out))
    return path


class TestConsentGate:
    def test_unapproved_pdf_is_denied(self, pdf: Path, tmp_path: Path) -> None:
        out = run_hook(str(pdf), tmpdir=tmp_path)
        decision = out["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        # The agent has to be told what to do instead, or it will just retry.
        assert "place, attach, upload" in decision["permissionDecisionReason"]
        assert "letter.pdf" in decision["permissionDecisionReason"]

    def test_unapproved_image_is_denied(self, tmp_path: Path) -> None:
        img = tmp_path / "scan.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 4096)
        out = run_hook(str(img), tmpdir=tmp_path)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_deny_names_the_exact_command_that_lifts_it(
        self, pdf: Path, tmp_path: Path
    ) -> None:
        """A gate the agent cannot open on request is a broken gate."""
        reason = run_hook(str(pdf), tmpdir=tmp_path)["hookSpecificOutput"][
            "permissionDecisionReason"
        ]
        marker = str(tmp_path / "agent-read-approved" / "letter.pdf")
        assert marker in reason
        assert "Do not run that command on your own initiative." in reason

    def test_other_file_types_are_untouched(self, tmp_path: Path) -> None:
        """The gate is for what a user hands over, not for the codebase."""
        src = tmp_path / "app.py"
        src.write_text("print('hi')\n")
        assert run_hook(str(src), tmpdir=tmp_path) == {}

    def test_non_read_tools_are_untouched(self, pdf: Path, tmp_path: Path) -> None:
        assert run_hook(str(pdf), tmpdir=tmp_path, tool="Bash") == {}

    def test_missing_file_is_left_to_read_to_report(self, tmp_path: Path) -> None:
        assert run_hook(str(tmp_path / "gone.pdf"), tmpdir=tmp_path) == {}


class TestCheapCopy:
    @pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler-utils absent")
    def test_approved_pdf_is_handed_over_as_text(self, pdf: Path, tmp_path: Path) -> None:
        approve("letter.pdf", tmp_path)
        out = run_hook(str(pdf), tmpdir=tmp_path)["hookSpecificOutput"]

        swapped = Path(out["updatedInput"]["file_path"])
        assert swapped != pdf, "the model was handed the original PDF"
        assert swapped.suffix == ".txt"
        assert "Salam Polyclinic verification letter" in swapped.read_text()
        assert "PDF text extracted" in out["permissionDecisionReason"]

    def test_approved_small_image_is_not_worth_shrinking(self, tmp_path: Path) -> None:
        img = tmp_path / "icon.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 1024)
        approve("icon.png", tmp_path)
        assert run_hook(str(img), tmpdir=tmp_path) == {}

    def test_approved_unreadable_image_falls_open(self, tmp_path: Path) -> None:
        """A hook that breaks Read is worse than a large image."""
        img = tmp_path / "broken.png"
        img.write_bytes(b"not an image" * 40_000)
        approve("broken.png", tmp_path)
        assert run_hook(str(img), tmpdir=tmp_path) == {}
