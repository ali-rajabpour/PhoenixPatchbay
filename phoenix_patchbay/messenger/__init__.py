"""Messenger abstraction layer — transport-agnostic protocols and registry."""

from phoenix_patchbay.messenger.commands import (
    DIRECT_COMMANDS,
    MULTIAGENT_COMMANDS,
    ORCHESTRATOR_COMMANDS,
    classify_command,
)
from phoenix_patchbay.messenger.multi import MultiBotAdapter
from phoenix_patchbay.messenger.notifications import (
    CompositeNotificationService,
    NotificationService,
)
from phoenix_patchbay.messenger.protocol import BotProtocol
from phoenix_patchbay.messenger.registry import create_bot
from phoenix_patchbay.messenger.send_opts import BaseSendOpts

__all__ = [
    "DIRECT_COMMANDS",
    "MULTIAGENT_COMMANDS",
    "ORCHESTRATOR_COMMANDS",
    "BaseSendOpts",
    "BotProtocol",
    "CompositeNotificationService",
    "MultiBotAdapter",
    "NotificationService",
    "classify_command",
    "create_bot",
]
