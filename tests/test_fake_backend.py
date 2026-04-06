import pytest

from proxmox_sdk import FakeBackend, VmNotFoundError


def test_add_vm_seeding() -> None:
    fb = FakeBackend()
    fb.add_vm(100, name="test", status="stopped")
    result = fb.get("nodes/pve/qemu/100/status/current")
    assert result["vmid"] == 100
    assert result["name"] == "test"
    assert result["status"] == "stopped"


def test_list_vms_via_cluster_resources() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    fb.add_vm(101)
    vms = fb.get("cluster/resources", type="vm")
    assert len(vms) == 2
    assert {v["vmid"] for v in vms} == {100, 101}


def test_start_transitions_status() -> None:
    fb = FakeBackend()
    fb.add_vm(100, status="stopped")
    fb.post("nodes/pve/qemu/100/status/start")
    vm = fb.get("nodes/pve/qemu/100/status/current")
    assert vm["status"] == "running"


def test_stop_transitions_status() -> None:
    fb = FakeBackend()
    fb.add_vm(100, status="running")
    fb.post("nodes/pve/qemu/100/status/stop")
    vm = fb.get("nodes/pve/qemu/100/status/current")
    assert vm["status"] == "stopped"


def test_delete_removes_vm() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    fb.delete("nodes/pve/qemu/100")
    with pytest.raises(KeyError):
        fb.get("nodes/pve/qemu/100/status/current")


def test_clone_creates_new_vm() -> None:
    fb = FakeBackend()
    fb.add_vm(9000, name="template")
    fb.post("nodes/pve/qemu/9000/clone", newid=200, name="cloned")
    vms = fb.get("cluster/resources", type="vm")
    assert any(v["vmid"] == 200 for v in vms)


def test_snapshot_round_trip() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    fb.post("nodes/pve/qemu/100/snapshots", snapname="snap-1")
    snaps = fb.get("nodes/pve/qemu/100/snapshots")
    assert any(s["name"] == "snap-1" for s in snaps)


def test_calls_tracking() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    fb.get("nodes/pve/qemu/100/status/current")
    fb.post("nodes/pve/qemu/100/status/start")
    assert len(fb.calls) == 2
    assert fb.calls[0][0] == "GET"
    assert fb.calls[1][0] == "POST"


def test_assert_called_with_passes() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    fb.post("nodes/pve/qemu/100/status/start")
    fb.assert_called_with("POST", "nodes/pve/qemu/100/status/start")


def test_assert_called_with_fails() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    with pytest.raises(AssertionError):
        fb.assert_called_with("POST", "nodes/pve/qemu/100/status/start")


def test_vm_not_found_raises() -> None:
    fb = FakeBackend()
    with pytest.raises(VmNotFoundError):
        fb.post("nodes/pve/qemu/999/status/start")


def test_wait_for_task_resolves_instantly() -> None:
    fb = FakeBackend()
    fb.add_vm(100)
    upid = fb.post("nodes/pve/qemu/100/status/start")
    fb.wait_for_task("pve", upid)  # should not raise or block
