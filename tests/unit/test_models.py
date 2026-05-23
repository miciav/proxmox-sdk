import pytest

from proxmox_sdk._backend import CommandResult
from proxmox_sdk.models import (
    NodeInfo,
    SnapshotInfo,
    TemplateInfo,
    VmInfo,
    VmMetrics,
    VmState,
)


# ------------------------------------------------------------------
# VmState
# ------------------------------------------------------------------


def test_vm_state_known_values() -> None:
    assert VmState("running") == VmState.RUNNING
    assert VmState("stopped") == VmState.STOPPED


def test_vm_state_unknown_falls_back() -> None:
    assert VmState("weird-state") == VmState.UNKNOWN


# ------------------------------------------------------------------
# VmInfo
# ------------------------------------------------------------------


def test_vm_info_from_api_maps_fields() -> None:
    raw = {
        "vmid": 100,
        "name": "my-vm",
        "node": "pve",
        "status": "running",
        "cpus": 4,
        "maxmem": 4 * 1024 * 1024 * 1024,
        "uptime": 7200,
        "template": False,
    }
    info = VmInfo.from_api(raw)
    assert info.vm_id == 100
    assert info.name == "my-vm"
    assert info.node == "pve"
    assert info.state == VmState.RUNNING
    assert info.cpu_count == 4
    assert info.memory_mb == 4096
    assert info.uptime_seconds == 7200
    assert info.template is False


def test_vm_info_from_api_prefers_configured_cpu_count() -> None:
    raw = {
        "vmid": 100,
        "name": "my-vm",
        "node": "pve",
        "status": "running",
        "cores": 2,
        "maxcpu": 8,
        "cpus": 4,
        "maxmem": 4 * 1024 * 1024 * 1024,
        "uptime": 7200,
        "template": False,
    }
    info = VmInfo.from_api(raw)
    assert info.cpu_count == 2


def test_vm_info_tags_parsed() -> None:
    raw = {
        "vmid": 1,
        "name": "x",
        "node": "pve",
        "status": "stopped",
        "cpus": 1,
        "maxmem": 1024 * 1024 * 1024,
        "uptime": 0,
        "tags": "k3s;docker",
    }
    info = VmInfo.from_api(raw)
    assert info.tags == ["k3s", "docker"]


# ------------------------------------------------------------------
# VmMetrics
# ------------------------------------------------------------------


def test_vm_metrics_cpu_pct_computed() -> None:
    raw = {
        "vmid": 100,
        "cpu": 0.05,
        "mem": 536870912,   # 512 MB
        "maxmem": 1073741824,  # 1 GB
        "netin": 0,
        "netout": 0,
        "diskread": 0,
        "diskwrite": 0,
    }
    m = VmMetrics.from_api(raw)
    assert m.cpu_pct == pytest.approx(5.0)
    assert m.mem_used_pct == pytest.approx(50.0)
    assert m.mem_used_bytes == 536870912
    assert m.mem_total_bytes == 1073741824


def test_vm_metrics_zero_maxmem_safe() -> None:
    raw = {
        "vmid": 100,
        "cpu": 0.0,
        "mem": 0,
        "maxmem": 0,
        "netin": 0,
        "netout": 0,
        "diskread": 0,
        "diskwrite": 0,
    }
    m = VmMetrics.from_api(raw)
    assert m.mem_used_pct == 0.0


# ------------------------------------------------------------------
# NodeInfo
# ------------------------------------------------------------------


def test_node_info_from_api() -> None:
    raw = {
        "node": "pve",
        "status": "online",
        "maxcpu": 16,
        "maxmem": 32 * 1024 * 1024 * 1024,
        "mem": 8 * 1024 * 1024 * 1024,
        "uptime": 86400,
    }
    node = NodeInfo.from_api(raw)
    assert node.name == "pve"
    assert node.status == "online"
    assert node.cpu_count == 16


# ------------------------------------------------------------------
# SnapshotInfo
# ------------------------------------------------------------------


def test_snapshot_info_from_api() -> None:
    raw = {
        "name": "snap-1",
        "description": "before upgrade",
        "snaptime": 1700000000,
        "parent": None,
    }
    snap = SnapshotInfo.from_api(raw, vm_id=100)
    assert snap.name == "snap-1"
    assert snap.description == "before upgrade"
    assert snap.vm_id == 100
    assert snap.created == 1700000000


# ------------------------------------------------------------------
# TemplateInfo
# ------------------------------------------------------------------


def test_template_info_from_api() -> None:
    raw = {"vmid": 9000, "name": "ubuntu-22", "node": "pve"}
    tmpl = TemplateInfo.from_api(raw)
    assert tmpl.vm_id == 9000
    assert tmpl.name == "ubuntu-22"


# ------------------------------------------------------------------
# CommandResult
# ------------------------------------------------------------------


def test_command_result_success_property() -> None:
    assert CommandResult(exit_code=0, stdout="ok", stderr="").success is True
    assert CommandResult(exit_code=1, stdout="", stderr="err").success is False
