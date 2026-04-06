"""Tests for CloudInitConfig model and its Proxmox API serialization."""

from proxmox_sdk.backends.fake import FakeBackend
from proxmox_sdk.models import CloudInitConfig


def test_cloud_init_to_api_params_full() -> None:
    cfg = CloudInitConfig(
        username="ubuntu",
        password="secret",
        ssh_keys=["ssh-rsa AAAA user@host"],
        ip_config="ip=dhcp",
        nameserver="8.8.8.8",
        searchdomain="local",
    )
    params = cfg.to_api_params()
    assert params["ciuser"] == "ubuntu"
    assert params["cipassword"] == "secret"
    assert "sshkeys" in params
    assert " " not in params["sshkeys"]   # spaces must be percent-encoded
    assert "%" in params["sshkeys"]        # encoding must have occurred
    assert params["ipconfig0"] == "ip=dhcp"
    assert params["nameserver"] == "8.8.8.8"
    assert params["searchdomain"] == "local"


def test_cloud_init_to_api_params_empty() -> None:
    cfg = CloudInitConfig()
    assert cfg.to_api_params() == {}


def test_cloud_init_to_api_params_omits_none_fields() -> None:
    cfg = CloudInitConfig(username="ubuntu")
    params = cfg.to_api_params()
    assert "cipassword" not in params
    assert "sshkeys" not in params
    assert "ipconfig0" not in params


def test_cloud_init_ssh_keys_url_encoded() -> None:
    cfg = CloudInitConfig(ssh_keys=["ssh-rsa AAAA key1", "ssh-rsa BBBB key2"])
    params = cfg.to_api_params()
    encoded = params["sshkeys"]
    # Must not contain literal spaces or newlines (they must be percent-encoded)
    assert " " not in encoded
    assert "\n" not in encoded
    # Must contain percent-encoding (spaces in "ssh-rsa AAAA" become %20)
    assert "%" in encoded
    # Round-trip must recover original
    from urllib.parse import unquote
    decoded = unquote(encoded)
    assert decoded == "ssh-rsa AAAA key1\nssh-rsa BBBB key2"


def test_cloud_init_empty_string_treated_as_absent() -> None:
    cfg = CloudInitConfig(username="", ip_config="")
    params = cfg.to_api_params()
    assert "ciuser" not in params
    assert "ipconfig0" not in params


def test_cloud_init_static_ip_config() -> None:
    cfg = CloudInitConfig(ip_config="ip=10.0.0.5/24,gw=10.0.0.1")
    params = cfg.to_api_params()
    assert params["ipconfig0"] == "ip=10.0.0.5/24,gw=10.0.0.1"


def test_fake_backend_stores_config_put() -> None:
    fb = FakeBackend()
    fb.add_vm(100, node="pve", name="test-vm")
    fb.put("nodes/pve/qemu/100/config", ciuser="ubuntu", ipconfig0="ip=dhcp")
    vm = fb.get("nodes/pve/qemu/100/config")
    assert vm["ciuser"] == "ubuntu"
    assert vm["ipconfig0"] == "ip=dhcp"


def test_fake_backend_get_config_returns_vm_dict() -> None:
    fb = FakeBackend()
    fb.add_vm(100, node="pve", name="my-vm")
    result = fb.get("nodes/pve/qemu/100/config")
    assert result["name"] == "my-vm"
    assert result["vmid"] == 100
