"""Tests for CloudInitConfig and ProxmoxVM.configure_cloud_init()."""

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
    assert "ssh-rsa" in params["sshkeys"]
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
    from urllib.parse import unquote
    decoded = unquote(params["sshkeys"])
    assert decoded == "ssh-rsa AAAA key1\nssh-rsa BBBB key2"


def test_cloud_init_static_ip_config() -> None:
    cfg = CloudInitConfig(ip_config="ip=10.0.0.5/24,gw=10.0.0.1")
    params = cfg.to_api_params()
    assert params["ipconfig0"] == "ip=10.0.0.5/24,gw=10.0.0.1"
