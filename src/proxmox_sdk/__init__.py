"""
proxmox-sdk: Pythonic SDK for Proxmox VE VM management.

Mirrors the multipass-sdk API design:
  https://github.com/miciav/multipass-sdk
"""

from proxmox_sdk.backends.fake import FakeBackend
from proxmox_sdk.backends.proxmoxer import ProxmoxerBackend
from proxmox_sdk.backends.ssh import FakeSshBackend, ParamikoSshBackend
from proxmox_sdk.routing import PortMapping, ProxmoxRoutingManager
from proxmox_sdk.client import ProxmoxClient
from proxmox_sdk.exceptions import (
    NodeNotFoundError,
    ProxmoxAPIError,
    ProxmoxAuthError,
    ProxmoxConnectionError,
    ProxmoxError,
    ProxmoxTimeoutError,
    SnapshotNotFoundError,
    TaskFailedError,
    VmNotFoundError,
    VmStateError,
)
from proxmox_sdk.models import (
    CloudInitConfig,
    CommandResult,
    NodeInfo,
    SnapshotInfo,
    TaskInfo,
    TemplateInfo,
    VmInfo,
    VmMetrics,
    VmState,
)
from proxmox_sdk.vm import ProxmoxVM

__all__ = [
    # Entry points
    "ProxmoxClient",
    "ProxmoxVM",
    # Models
    "CloudInitConfig",
    "CommandResult",
    "NodeInfo",
    "SnapshotInfo",
    "TaskInfo",
    "TemplateInfo",
    "VmInfo",
    "VmMetrics",
    "VmState",
    # Exceptions
    "ProxmoxError",
    "ProxmoxAuthError",
    "ProxmoxConnectionError",
    "ProxmoxAPIError",
    "VmNotFoundError",
    "VmStateError",
    "NodeNotFoundError",
    "ProxmoxTimeoutError",
    "SnapshotNotFoundError",
    "TaskFailedError",
    # Backends
    "FakeBackend",
    "ProxmoxerBackend",
    "FakeSshBackend",
    "ParamikoSshBackend",
    # Routing / NAT
    "ProxmoxRoutingManager",
    "PortMapping",
]
