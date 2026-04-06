from __future__ import annotations


def parse_proxmox_url(api_url: str) -> tuple[str, int]:
    """
    Extract host and port from a Proxmox API URL.

    Handles forms like:
      https://192.168.1.100:8006/api2/json
      http://proxmox-host:8006
      proxmox-host

    Returns (host, port).
    """
    url = api_url.replace("https://", "").replace("http://", "")
    host_port = url.split("/")[0]
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        return host, int(port_str)
    return host_port, 8006
