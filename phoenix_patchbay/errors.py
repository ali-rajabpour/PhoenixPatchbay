"""Project-level exception hierarchy."""


class PatchbayError(Exception):
    """Base for all patchbay exceptions."""


class CLIError(PatchbayError):
    """CLI execution failed."""


class WorkspaceError(PatchbayError):
    """Workspace initialization or access failed."""


class SessionError(PatchbayError):
    """Session persistence or lifecycle failed."""


class CronError(PatchbayError):
    """Cron job scheduling or execution failed."""


class StreamError(PatchbayError):
    """Streaming output failed."""


class SecurityError(PatchbayError):
    """Security violation detected."""


class PathValidationError(SecurityError):
    """File path failed validation."""


class WebhookError(PatchbayError):
    """Webhook server or dispatch failed."""
