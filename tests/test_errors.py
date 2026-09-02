"""Tests for the exception hierarchy."""

from phoenix_patchbay.errors import (
    CLIError,
    PatchbayError,
    PathValidationError,
    SecurityError,
    WorkspaceError,
)


def test_base_error_is_exception() -> None:
    assert issubclass(PatchbayError, Exception)


def test_cli_error_inherits_base() -> None:
    err = CLIError("cli broke")
    assert isinstance(err, PatchbayError)
    assert str(err) == "cli broke"


def test_workspace_error_inherits_base() -> None:
    assert isinstance(WorkspaceError("no workspace"), PatchbayError)


def test_security_error_inherits_base() -> None:
    assert isinstance(SecurityError("blocked"), PatchbayError)


def test_path_validation_error_inherits_security() -> None:
    err = PathValidationError("outside root")
    assert isinstance(err, SecurityError)
    assert isinstance(err, PatchbayError)


def test_catch_all_with_base() -> None:
    """All subclasses catchable via PatchbayError."""
    for cls in (CLIError, WorkspaceError, SecurityError, PathValidationError):
        try:
            raise cls("test")
        except PatchbayError:
            pass
