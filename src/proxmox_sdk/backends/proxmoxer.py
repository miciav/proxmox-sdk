from __future__ import annotations

import time
from typing import Any

from proxmox_sdk.exceptions import (
    ProxmoxAPIError,
    ProxmoxTimeoutError,
    TaskFailedError,
    VmNotFoundError,
)


class ProxmoxerBackend:
    """
    Real backend that delegates to the proxmoxer library.

    Translates flat path strings like "nodes/pve/qemu/100/status/start"
    into proxmoxer attribute-chain calls.
    """

    def __init__(self, proxmox_api: Any) -> None:
        self._api = proxmox_api

    def get(self, path: str, **params: Any) -> Any:
        return self._call("get", path, **params)

    def post(self, path: str, **data: Any) -> Any:
        return self._call("post", path, **data)

    def put(self, path: str, **data: Any) -> Any:
        return self._call("put", path, **data)

    def delete(self, path: str, **params: Any) -> Any:
        return self._call("delete", path, **params)

    def wait_for_task(
        self, node: str, upid: str, timeout: float = 60
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = self.get(f"nodes/{node}/tasks/{upid}/status")
                if result.get("status") == "stopped":
                    exit_status = result.get("exitstatus", "")
                    if exit_status != "OK":
                        raise TaskFailedError(upid, exit_status)
                    return
            except (KeyError, AttributeError):
                pass
            time.sleep(1)
        raise ProxmoxTimeoutError(0, "wait_for_task", timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> Any:
        """Walk the proxmoxer attribute/call chain from a flat path string."""
        resource = self._api
        for segment in path.strip("/").split("/"):
            if segment.lstrip("-").isdigit():
                resource = resource(segment)
            else:
                resource = getattr(resource, segment)
        return resource

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resource = self._resolve(path)
            return getattr(resource, method)(**kwargs)
        except Exception as exc:
            self._translate_exception(exc, path)
            raise  # unreachable, but satisfies type checker

    @staticmethod
    def _translate_exception(exc: Exception, path: str) -> None:
        """Re-raise proxmoxer exceptions as proxmox-sdk exceptions."""
        # proxmoxer raises ResourceException; we check by name to avoid
        # importing proxmoxer in the exception module
        exc_type = type(exc).__name__
        if exc_type == "ResourceException":
            status_code = getattr(exc, "status_code", 0)
            content = str(getattr(exc, "content", str(exc)))
            if status_code == 404 or "does not exist" in content.lower():
                raise VmNotFoundError(path) from exc
            raise ProxmoxAPIError(status_code, content, path) from exc
