from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VmState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> "VmState":
        return cls.UNKNOWN


@dataclass
class VmInfo:
    vm_id: int
    name: str
    node: str
    state: VmState
    cpu_count: int
    memory_mb: int
    uptime_seconds: int
    ipv4: list[str] = field(default_factory=list)
    template: bool = False
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "VmInfo":
        """Map from cluster.resources or nodes/{n}/qemu/{id}/status/current response."""
        tags_raw = data.get("tags", "") or ""
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
        maxmem = data.get("maxmem") or 0
        return cls(
            vm_id=int(data.get("vmid", 0)),
            name=data.get("name", ""),
            node=data.get("node", ""),
            state=VmState(data.get("status", "unknown")),
            cpu_count=int(data.get("cpus", data.get("cpu_count", 1))),
            memory_mb=maxmem // (1024 * 1024) if maxmem else 0,
            uptime_seconds=int(data.get("uptime", 0)),
            ipv4=[],
            template=bool(data.get("template", False)),
            tags=tags,
        )


@dataclass
class VmMetrics:
    vm_id: int
    cpu_pct: float
    mem_used_bytes: int
    mem_total_bytes: int
    mem_used_pct: float
    net_in_bytes: int
    net_out_bytes: int
    disk_read_bytes: int
    disk_write_bytes: int

    @classmethod
    def from_api(cls, data: dict) -> "VmMetrics":
        """Map from cluster.resources VM entry (same shape as app.py vm_metrics)."""
        maxmem = data.get("maxmem") or 0
        mem = data.get("mem") or 0
        mem_pct = round(mem / maxmem * 100, 2) if maxmem else 0.0
        cpu_pct = round((data.get("cpu") or 0) * 100, 2)
        return cls(
            vm_id=int(data.get("vmid", 0)),
            cpu_pct=cpu_pct,
            mem_used_bytes=int(mem),
            mem_total_bytes=int(maxmem),
            mem_used_pct=mem_pct,
            net_in_bytes=int(data.get("netin", 0)),
            net_out_bytes=int(data.get("netout", 0)),
            disk_read_bytes=int(data.get("diskread", 0)),
            disk_write_bytes=int(data.get("diskwrite", 0)),
        )


@dataclass
class NodeInfo:
    name: str
    status: str
    cpu_count: int
    memory_total_bytes: int
    memory_used_bytes: int
    uptime_seconds: int

    @classmethod
    def from_api(cls, data: dict) -> "NodeInfo":
        return cls(
            name=data.get("node", ""),
            status=data.get("status", "unknown"),
            cpu_count=int(data.get("maxcpu", 0)),
            memory_total_bytes=int(data.get("maxmem", 0)),
            memory_used_bytes=int(data.get("mem", 0)),
            uptime_seconds=int(data.get("uptime", 0)),
        )


@dataclass
class SnapshotInfo:
    name: str
    vm_id: int
    created: int
    description: str = ""
    parent: str | None = None

    @classmethod
    def from_api(cls, data: dict, vm_id: int = 0) -> "SnapshotInfo":
        return cls(
            name=data.get("name", ""),
            vm_id=vm_id,
            created=int(data.get("snaptime", 0)),
            description=data.get("description", ""),
            parent=data.get("parent") or None,
        )


@dataclass
class TemplateInfo:
    vm_id: int
    name: str
    node: str
    description: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "TemplateInfo":
        return cls(
            vm_id=int(data.get("vmid", 0)),
            name=data.get("name", ""),
            node=data.get("node", ""),
            description=data.get("description", ""),
        )


@dataclass
class TaskInfo:
    upid: str
    node: str
    type: str
    status: str
    exit_status: str | None

    @classmethod
    def from_api(cls, data: dict) -> "TaskInfo":
        return cls(
            upid=data.get("upid", ""),
            node=data.get("node", ""),
            type=data.get("type", ""),
            status=data.get("status", ""),
            exit_status=data.get("exitstatus") or None,
        )


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0
