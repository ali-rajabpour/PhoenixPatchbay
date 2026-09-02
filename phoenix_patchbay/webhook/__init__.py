"""Webhook system: HTTP ingress for external event triggers."""

from phoenix_patchbay.webhook.manager import WebhookManager
from phoenix_patchbay.webhook.models import WebhookEntry, WebhookResult

__all__ = ["WebhookEntry", "WebhookManager", "WebhookResult"]
