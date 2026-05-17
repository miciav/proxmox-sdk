"""
Tests for ProxmoxRoutingManager.

All tests use FakeSshBackend — no real SSH connection needed.
The fake backend simulates the Proxmox host filesystem and command output.
"""

import pytest

from proxmox_sdk.backends.ssh import FakeSshBackend
from proxmox_sdk.routing import PortMapping, ProxmoxRoutingManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BLANK_INTERFACES = """\
auto lo
iface lo inet loopback

auto vmbr0
iface vmbr0 inet static
    address 192.168.1.100/24
    gateway 192.168.1.1
    bridge-ports eth0
    bridge-stp off

auto vmbr1
iface vmbr1 inet static
    address 10.0.0.1/24
    bridge-ports none
    bridge-stp off

"""


def make_backend(interfaces_content: str = BLANK_INTERFACES) -> FakeSshBackend:
    fb = FakeSshBackend()
    fb.seed_file("/etc/network/interfaces", interfaces_content)
    # Simulate ss -tln: ports 22 and 80 in use
    fb.seed_response(
        "ss -tln",
        0,
        "State  Recv-Q  Send-Q  Local Address:Port\n"
        "LISTEN 0       128     *:22\n"
        "LISTEN 0       128     *:80\n",
    )
    return fb


def make_manager(backend: FakeSshBackend) -> ProxmoxRoutingManager:
    return ProxmoxRoutingManager(
        backend,
        interfaces_file="/etc/network/interfaces",
        external_iface="vmbr0",
        internal_iface="vmbr1",
        port_range=(20000, 21000),
    )


SAMPLE_MAPPINGS = [
    PortMapping(
        vm_id=100,
        vm_name="node-1",
        vm_ip="10.0.0.10",
        vm_port=22,
        service="SSH",
        vm_user="ubuntu",
    ),
    PortMapping(
        vm_id=100,
        vm_name="node-1",
        vm_ip="10.0.0.10",
        vm_port=6443,
        service="k3s",
    ),
    PortMapping(
        vm_id=101,
        vm_name="node-2",
        vm_ip="10.0.0.11",
        vm_port=22,
        service="SSH",
        vm_user="ubuntu",
    ),
]

# ---------------------------------------------------------------------------
# add_rules
# ---------------------------------------------------------------------------


def test_add_rules_assigns_host_ports() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))

    assert len(assigned) == 3
    assert all(m.host_port is not None for m in assigned)
    host_ports = {m.host_port for m in assigned}
    # All distinct
    assert len(host_ports) == 3


def test_add_rules_ports_in_range() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))
    for m in assigned:
        assert 20000 <= m.host_port < 21000  # type: ignore[operator]


def test_add_rules_ports_not_already_in_use() -> None:
    backend = make_backend()
    # Seed some already-used ports at the start of the range
    backend.seed_response(
        "ss -tln",
        0,
        "State  Recv-Q  Send-Q  Local Address:Port\n"
        "LISTEN 0       128     *:20000\n"
        "LISTEN 0       128     *:20001\n",
    )
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))
    for m in assigned:
        assert m.host_port not in (20000, 20001)  # type: ignore[operator]


def test_add_rules_writes_post_up_and_post_down() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))

    content = backend.read_file("/etc/network/interfaces")
    for m in assigned:
        assert f"--dport {m.host_port}" in content
        assert f"--to {m.vm_ip}:{m.vm_port}" in content
        assert "post-up iptables -t nat -A PREROUTING" in content
        assert "post-down iptables -t nat -D PREROUTING" in content
        assert m.tag() in content


def test_add_rules_flushes_and_reloads() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    mgr.add_rules(list(SAMPLE_MAPPINGS))
    backend.assert_ran("iptables -t nat -F PREROUTING")
    backend.assert_ran("ifreload --all")


def test_add_rules_idempotent() -> None:
    """Calling add_rules twice should not duplicate rules."""
    backend = make_backend()
    mgr = make_manager(backend)
    _first = mgr.add_rules(list(SAMPLE_MAPPINGS))
    second = mgr.add_rules(list(SAMPLE_MAPPINGS))

    content = backend.read_file("/etc/network/interfaces")
    # Each tag should appear exactly twice (post-up + post-down)
    for m in second:
        assert content.count(m.tag()) == 2


# ---------------------------------------------------------------------------
# remove_rules
# ---------------------------------------------------------------------------


def test_remove_rules_clears_entries() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))

    mgr.remove_rules(assigned)

    content = backend.read_file("/etc/network/interfaces")
    for m in assigned:
        assert m.tag() not in content


def test_remove_rules_flushes_and_reloads() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))
    backend.commands.clear()  # reset call log

    mgr.remove_rules(assigned)
    backend.assert_ran("iptables -t nat -F PREROUTING")
    backend.assert_ran("ifreload --all")


def test_remove_rules_preserves_unrelated_lines() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))
    mgr.remove_rules(assigned)

    content = backend.read_file("/etc/network/interfaces")
    assert "iface vmbr0 inet static" in content
    assert "iface vmbr1 inet static" in content


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


def test_list_rules_empty_initially() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assert mgr.list_rules() == []


def test_list_rules_returns_added_rules() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    assigned = mgr.add_rules(list(SAMPLE_MAPPINGS))

    rules = mgr.list_rules()
    assert len(rules) == 3
    rule_services = {r.service for r in rules}
    assert rule_services == {"SSH", "k3s"}

    for rule in rules:
        # Find the matching assigned mapping
        match = next(
            (m for m in assigned if m.vm_id == rule.vm_id and m.service == rule.service),
            None,
        )
        assert match is not None
        assert rule.host_port == match.host_port
        assert rule.vm_ip == match.vm_ip
        assert rule.vm_port == match.vm_port


# ---------------------------------------------------------------------------
# flush_rules
# ---------------------------------------------------------------------------


def test_flush_rules_calls_iptables_and_ifreload() -> None:
    backend = make_backend()
    mgr = make_manager(backend)
    mgr.flush_rules()
    backend.assert_ran("iptables -t nat -F PREROUTING")
    backend.assert_ran("ifreload --all")


# ---------------------------------------------------------------------------
# Port range exhaustion
# ---------------------------------------------------------------------------


def test_not_enough_ports_raises() -> None:
    backend = make_backend()
    mgr = ProxmoxRoutingManager(
        backend,
        interfaces_file="/etc/network/interfaces",
        port_range=(20000, 20002),  # only 2 ports available
    )
    with pytest.raises(RuntimeError, match="Not enough available ports"):
        mgr.add_rules(list(SAMPLE_MAPPINGS))  # needs 3


# ---------------------------------------------------------------------------
# PortMapping dataclass
# ---------------------------------------------------------------------------


def test_port_mapping_tag_format() -> None:
    m = PortMapping(vm_id=42, vm_name="my-vm", vm_ip="10.0.0.1", vm_port=22, service="SSH")
    assert m.tag() == "# VM 42 (my-vm) - SSH"


def test_port_mapping_host_port_none_by_default() -> None:
    m = PortMapping(vm_id=1, vm_name="x", vm_ip="1.1.1.1", vm_port=22, service="SSH")
    assert m.host_port is None


# ---------------------------------------------------------------------------
# Existing rules in interfaces file are respected
# ---------------------------------------------------------------------------


def test_existing_rules_not_reassigned_same_port() -> None:
    """Ports already in the interfaces file must not be reused."""
    # Pre-populate file with an existing rule at port 20000
    existing = BLANK_INTERFACES + (
        "    post-up iptables -t nat -A PREROUTING -i vmbr0 -p tcp --dport 20000 "
        "-j DNAT --to 10.0.0.99:22 # VM 999 (old-vm) - SSH\n"
    )
    backend = make_backend(existing)
    mgr = make_manager(backend)

    assigned = mgr.add_rules([SAMPLE_MAPPINGS[0]])
    assert assigned[0].host_port != 20000
