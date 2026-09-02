"""CLI layer: provider abstraction, process tracking, streaming."""

from phoenix_patchbay.cli.auth import AuthResult as AuthResult
from phoenix_patchbay.cli.auth import AuthStatus as AuthStatus
from phoenix_patchbay.cli.auth import check_all_auth as check_all_auth
from phoenix_patchbay.cli.base import BaseCLI as BaseCLI
from phoenix_patchbay.cli.base import CLIConfig as CLIConfig
from phoenix_patchbay.cli.coalescer import CoalesceConfig as CoalesceConfig
from phoenix_patchbay.cli.coalescer import StreamCoalescer as StreamCoalescer
from phoenix_patchbay.cli.factory import create_cli as create_cli
from phoenix_patchbay.cli.process_registry import ProcessRegistry as ProcessRegistry
from phoenix_patchbay.cli.service import CLIService as CLIService
from phoenix_patchbay.cli.service import CLIServiceConfig as CLIServiceConfig
from phoenix_patchbay.cli.types import AgentRequest as AgentRequest
from phoenix_patchbay.cli.types import AgentResponse as AgentResponse
from phoenix_patchbay.cli.types import CLIResponse as CLIResponse

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AuthResult",
    "AuthStatus",
    "BaseCLI",
    "CLIConfig",
    "CLIResponse",
    "CLIService",
    "CLIServiceConfig",
    "CoalesceConfig",
    "ProcessRegistry",
    "StreamCoalescer",
    "check_all_auth",
    "create_cli",
]
