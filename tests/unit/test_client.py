import pytest

from proxmox_sdk import FakeBackend, ProxmoxClient, VmInfo, VmNotFoundError
from proxmox_sdk.models import CloudInitConfig, VmState


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
    vm = client.get_vm("stopped-vm")
    assert vm.vm_id == 100


def test_find_vm_not_found(client: ProxmoxClient) -> None:
    with pytest.raises(VmNotFoundError) as exc_info:
        client.get_vm("nonexistent")
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


def test_list_templates_returns_hardware_fields(
    fake_backend: FakeBackend,
) -> None:
    fake_backend.add_vm(
        9001,
        node="pve",
        name="debian-template",
        status="stopped",
        template=True,
        maxcpu=2,
        maxmem=2 * 1024 * 1024 * 1024,
    )
    client = ProxmoxClient(host="x", user="x", node="pve", backend=fake_backend)
    templates = client.list_templates()
    debian_tmpl = [t for t in templates if t.name == "debian-template"][0]
    assert debian_tmpl.cores == 2
    assert debian_tmpl.memory_mb == 2048


def test_find_template_by_name(
    fake_backend: FakeBackend,
) -> None:
    fake_backend.add_vm(
        9001,
        node="pve",
        name="custom-template",
        status="stopped",
        template=True,
        maxcpu=4,
        maxmem=4 * 1024 * 1024 * 1024,
    )
    client = ProxmoxClient(host="x", user="x", node="pve", backend=fake_backend)
    t = client.find_template("custom-template")
    assert t.vm_id == 9001
    assert t.name == "custom-template"
    assert t.cores == 4
    assert t.memory_mb == 4096


def test_find_template_raises_if_not_found(
    client: ProxmoxClient,
) -> None:
    with pytest.raises(VmNotFoundError):
        client.find_template("nonexistent-template")


def test_create_vm_calls_clone_then_start(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.launch("new-vm", template_id=9000, start=True)
    assert vm.vm_id is not None
    # Should have called POST clone and POST start
    methods_paths = [(m, p) for m, p, _ in fake_backend.calls]
    assert any("clone" in p for _, p in methods_paths)
    assert any("start" in p for _, p in methods_paths)


def test_create_vm_no_start(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    client.launch("lazy-vm", template_id=9000, start=False)
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
    client.purge()
    # VM 100 (stopped) and 9000 (template, stopped) should be deleted;
    # VM 101 (running) should remain
    remaining = client.list()
    for vm in remaining:
        assert vm.state == VmState.RUNNING


def test_create_vm_with_cloud_init_applies_config(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    cfg = CloudInitConfig(username="ubuntu", ip_config="ip=dhcp")
    vm = client.launch("ci-vm", template_id=9000, cloud_init_config=cfg, start=False)

    fake_backend.assert_called_with("PUT", f"nodes/pve/qemu/{vm.vm_id}/config")
    stored = fake_backend.get(f"nodes/pve/qemu/{vm.vm_id}/config")
    assert stored["ciuser"] == "ubuntu"
    assert stored["ipconfig0"] == "ip=dhcp"


def test_create_vm_without_cloud_init_does_not_call_config(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    client.launch("plain-vm", template_id=9000, start=False)
    calls = [(m, p) for m, p, _ in fake_backend.calls]
    assert not any(p.endswith("/config") for _, p in calls)


def test_create_vm_applies_cores_and_memory(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.launch("hw-vm", template_id=9000, cores=4, memory_mb=4096, start=False)
    stored = fake_backend.get(f"nodes/pve/qemu/{vm.vm_id}/config")
    assert stored["cores"] == 4
    assert stored["memory"] == 4096


def test_create_vm_info_reports_configured_cores(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.launch("info-vm", template_id=9000, cores=2, start=False)
    assert vm.info().cpu_count == 2


def test_create_vm_uses_long_task_timeout(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    seen_timeouts: list[float] = []

    def wait_for_task(node: str, upid: str, timeout: float = 60) -> None:
        seen_timeouts.append(timeout)

    fake_backend.wait_for_task = wait_for_task  # type: ignore[method-assign]

    client.launch("timeout-vm", template_id=9000, start=False)
    assert seen_timeouts == [300.0]


def test_create_vm_resizes_disk(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.launch("disk-vm", template_id=9000, disk_gb=50, start=False)
    fake_backend.assert_called_with("PUT", f"nodes/pve/qemu/{vm.vm_id}/resize")


def test_create_vm_no_config_when_no_hw_params(
    client: ProxmoxClient, fake_backend: FakeBackend
) -> None:
    vm = client.launch("plain-vm", template_id=9000, start=False)
    # No PUT /config call should be made for hw (cloud_init is also None here)
    hw_config_calls = [
        (m, p) for m, p, _ in fake_backend.calls
        if m == "PUT" and p == f"nodes/pve/qemu/{vm.vm_id}/config"
    ]
    assert hw_config_calls == []
