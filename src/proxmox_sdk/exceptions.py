from __future__ import annotations


class ProxmoxError(Exception):
    """Base class for all proxmox-sdk errors."""


class ProxmoxAuthError(ProxmoxError):
    """Authentication or authorization failed."""

    def __init__(self, host: str, user: str) -> None:
        self.host = host
        self.user = user
        super().__init__(f"Authentication failed for user '{user}' on host '{host}'")


class ProxmoxConnectionError(ProxmoxError):
    """Could not reach the Proxmox host."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        super().__init__(f"Could not connect to Proxmox at {host}:{port}")


class ProxmoxAPIError(ProxmoxError):
    """Proxmox API returned an error response."""

    def __init__(self, status_code: int, message: str, path: str) -> None:
        self.status_code = status_code
        self.message = message
        self.path = path
        super().__init__(
            f"Proxmox API error {status_code} at '{path}': {message}"
        )


class VmNotFoundError(ProxmoxError):
    """No VM matching the given ID or name."""

    def __init__(self, identifier: int | str) -> None:
        self.identifier = identifier
        super().__init__(f"VM not found: {identifier!r}")


class VmStateError(ProxmoxError):
    """Operation not valid for the VM's current state."""

    def __init__(self, vm_id: int, current: str, required: str) -> None:
        self.vm_id = vm_id
        self.current = current
        self.required = required
        super().__init__(
            f"VM {vm_id} is {current!r}, but operation requires {required!r}"
        )


class NodeNotFoundError(ProxmoxError):
    """Specified node does not exist in the cluster."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Node not found: {name!r}")


class ProxmoxTimeoutError(ProxmoxError):
    """A wait operation exceeded its timeout."""

    def __init__(self, vm_id: int, operation: str, timeout: float) -> None:
        self.vm_id = vm_id
        self.operation = operation
        self.timeout = timeout
        super().__init__(
            f"VM {vm_id}: '{operation}' timed out after {timeout}s"
        )


class SnapshotNotFoundError(ProxmoxError):
    """Specified snapshot does not exist on the VM."""

    def __init__(self, vm_id: int, snapshot: str) -> None:
        self.vm_id = vm_id
        self.snapshot = snapshot
        super().__init__(f"Snapshot {snapshot!r} not found on VM {vm_id}")


class TaskFailedError(ProxmoxError):
    """An async Proxmox task finished with a non-OK exit status."""

    def __init__(self, upid: str, exit_status: str) -> None:
        self.upid = upid
        self.exit_status = exit_status
        super().__init__(f"Task {upid!r} failed with status: {exit_status}")
