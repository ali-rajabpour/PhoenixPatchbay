"""Multi-agent architecture: supervisor, bus, and inter-agent communication."""

from phoenix_patchbay.multiagent.bus import InterAgentBus
from phoenix_patchbay.multiagent.health import AgentHealth
from phoenix_patchbay.multiagent.models import SubAgentConfig
from phoenix_patchbay.multiagent.supervisor import AgentSupervisor

__all__ = ["AgentHealth", "AgentSupervisor", "InterAgentBus", "SubAgentConfig"]
