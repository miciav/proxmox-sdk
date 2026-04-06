from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProxmoxBackend(Protocol):
    """
    Abstracts all Proxmox API calls.

    Paths are flat strings, e.g. "nodes/pve/qemu/100/status/start".
    The backend owns the translation from path + kwargs to the actual
    HTTP call (or in-memory mutation for FakeBackend).
    """

    def get(self, path: str, **params: Any) -> Any: ...

    def post(self, path: str, **data: Any) -> Any: ...

    def put(self, path: str, **data: Any) -> Any: ...

    def delete(self, path: str, **params: Any) -> Any: ...

    def wait_for_task(
        self, node: str, upid: str, timeout: float = 60
    ) -> None: ...
