import pytest

from proxmox_sdk import FakeBackend, ProxmoxClient, VmInfo, VmNotFoundError
from proxmox_sdk.models import VmState


def test_list_returns_all_vms(client: ProxmoxClient) -> None:
    vms = client.list()
    assert len(vms) == 3
    assert all(isinstance(v, VmInfo) for v in vms)


def test_list_node_filter(client: ProxmoxClient) -> None:
    vms = client.list(node="pve")
    assert len(vms) == 3


def test_get_vm_returns_proxmox_vm(client: ProxmoxClient) -> None:
    from proxmox_sdk import ProxmoxVM

    vm = client.get_vm(100)
    assert vm.vm_id == 100
    assert vm.node == "pve"
    assert isinstance(vm, ProxmoxVM)


def test_get_vm_raises_not_found(client: ProxmoxClient) -> None:
    with pytest.raises(VmNotFoundError) as exc_info:
        client.get_vm(999)
    assert exc_info.value.identifier == 999


def test_find_vm_by_name(client: ProxmoxClient) -> None:
    vm = client.find_vm("stopped-vm")
    assert vm.vm_id == 100


def test_find_vm_not_found(client: ProxmoxClient) -> None:
    with pytest.raises(VmNotFoundError) as exc_info:
        client.find_vm("nonexistent")
    assert exc_info.value.identifier == "nonexistent"


def test_list_nodes(client: ProxmoxClient) -> None:
    from proxmox_sdk import NodeInfo

    nodes = client.list_nodes()
    assert len(nodes) == 1
    assert isinstance(nodes[0], NodeInfo)
    assert nodes[0].name == "pve"


def test_list_templates(client: ProxmoxClient) -> None:
    templates = client.list_templates()
    assert len(templates) == 1
    assert templates[0].vm_id == 9000
    assert templates[0].name == "ubuntu-template"


def test_create_vm_calls_clone_then_start(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.create_vm("new-vm", template_id=9000, start=True)
    assert vm.vm_id is not None
    # Should have called POST clone and POST start
    methods_paths = [(m, p) for m, p, _ in fake_backend.calls]
    assert any("clone" in p for _, p in methods_paths)
    assert any("start" in p for _, p in methods_paths)


def test_create_vm_no_start(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    client.create_vm("lazy-vm", template_id=9000, start=False)
    methods_paths = [(m, p) for m, p, _ in fake_backend.calls]
    assert not any("start" in p for _, p in methods_paths)


def test_from_url_parses_host_and_port() -> None:
    from proxmox_sdk._utils import parse_proxmox_url

    host, port = parse_proxmox_url("https://192.168.1.5:8006/api2/json")
    assert host == "192.168.1.5"
    assert port == 8006

    host2, port2 = parse_proxmox_url("proxmox-host")
    assert host2 == "proxmox-host"
    assert port2 == 8006


def test_purge_stopped(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    client.purge_stopped()
    # VM 100 (stopped) and 9000 (template, stopped) should be deleted;
    # VM 101 (running) should remain
    remaining = client.list()
    for vm in remaining:
        assert vm.state == VmState.RUNNING
