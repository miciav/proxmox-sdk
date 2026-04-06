import pytest

from proxmox_sdk import (
    FakeBackend,
    ProxmoxClient,
    ProxmoxTimeoutError,
    SnapshotNotFoundError,
    VmNotFoundError,
)
from proxmox_sdk.models import VmState


def test_info_returns_vm_info(client: ProxmoxClient) -> None:
    from proxmox_sdk import VmInfo

    vm = client.get_vm(100)
    info = vm.info()
    assert isinstance(info, VmInfo)
    assert info.vm_id == 100
    assert info.name == "stopped-vm"
    assert info.state == VmState.STOPPED


def test_start_transitions_to_running(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    vm.start()
    assert vm.info().state == VmState.RUNNING


def test_stop_transitions_to_stopped(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(101)
    vm.stop()
    assert vm.info().state == VmState.STOPPED


def test_restart_keeps_running(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(101)
    vm.restart()
    assert vm.info().state == VmState.RUNNING


def test_delete_removes_vm(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    vm.delete(purge=True)
    with pytest.raises(VmNotFoundError):
        client.get_vm(100)


def test_clone_creates_new_vm(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    cloned = vm.clone(200, "cloned-vm")
    assert cloned.vm_id == 200
    # New VM should be listed
    vms = client.list()
    assert any(v.vm_id == 200 for v in vms)


def test_snapshot_round_trip(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    snap = vm.snapshot("snap-1", description="test snapshot")
    assert snap.name == "snap-1"
    assert snap.vm_id == 100

    snaps = vm.list_snapshots()
    assert any(s.name == "snap-1" for s in snaps)


def test_restore_known_snapshot(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    vm.snapshot("before")
    vm.restore("before")  # should not raise


def test_restore_unknown_snapshot_raises(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    with pytest.raises(SnapshotNotFoundError):
        vm.restore("nonexistent")


def test_wait_for_ip_raises_timeout(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    with pytest.raises(ProxmoxTimeoutError) as exc_info:
        vm.wait_for_ip(timeout=0.05)
    assert exc_info.value.vm_id == 100
    assert exc_info.value.operation == "wait_for_ip"


def test_metrics_returns_vm_metrics(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    from proxmox_sdk import VmMetrics

    vm = client.get_vm(101)
    m = vm.metrics()
    assert isinstance(m, VmMetrics)
    assert m.vm_id == 101
    assert m.cpu_pct == pytest.approx(5.0, abs=0.1)
    assert m.mem_used_pct == pytest.approx(25.0, abs=0.1)


def test_resize_disk_calls_put(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.get_vm(100)
    vm.resize_disk("scsi0", "+10G")
    fake_backend.assert_called_with("PUT", "nodes/pve/qemu/100/resize")
