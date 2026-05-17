from __future__ import annotations

from typing import Any, List

from proxmox_sdk._utils import parse_proxmox_url
from proxmox_sdk.backends.protocol import ProxmoxBackend
from proxmox_sdk.exceptions import VmNotFoundError
from proxmox_sdk.models import CloudInitConfig, NodeInfo, TemplateInfo, VmInfo
from proxmox_sdk.vm import ProxmoxVM


class ProxmoxClient:
    """
    Entry point for the proxmox-sdk.

    Usage::

        client = ProxmoxClient(host="192.168.1.100", user="root@pam", password="secret")
        vms = client.list()
        vm = client.get_vm(100)
        vm.start()

    For testing, inject a FakeBackend::

        from proxmox_sdk.backends.fake import FakeBackend
        fake = FakeBackend()
        fake.add_vm(100, name="test-vm")
        client = ProxmoxClient(host="x", user="x", backend=fake)
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str | None = None,
        token_name: str | None = None,
        token_value: str | None = None,
        port: int = 8006,
        verify_ssl: bool = False,
        node: str | None = None,
        backend: ProxmoxBackend | None = None,
    ) -> None:
        self._host = host
        self._user = user
        self._node = node

        if backend is not None:
            self._backend = backend
        else:
            self._backend = self._build_backend(
                host=host,
                user=user,
                password=password,
                token_name=token_name,
                token_value=token_value,
                port=port,
                verify_ssl=verify_ssl,
            )

    @classmethod
    def from_url(
        cls,
        api_url: str,
        user: str,
        password: str | None = None,
        *,
        token_name: str | None = None,
        token_value: str | None = None,
        verify_ssl: bool = False,
        node: str | None = None,
    ) -> "ProxmoxClient":
        """
        Construct from a full Proxmox API URL.

        Mirrors the URL parsing logic from connect_proxmox() in the deployer::

            client = ProxmoxClient.from_url(
                "https://192.168.1.100:8006/api2/json",
                user="root@pam",
                password="secret",
            )
        """
        host, port = parse_proxmox_url(api_url)
        return cls(
            host=host,
            user=user,
            password=password,
            token_name=token_name,
            token_value=token_value,
            port=port,
            verify_ssl=verify_ssl,
            node=node,
        )

    # ------------------------------------------------------------------
    # VM queries
    # ------------------------------------------------------------------

    def get_vm(self, vm_id: int | str) -> ProxmoxVM:
        """Return a ProxmoxVM by numeric ID. Raises VmNotFoundError if missing."""
        vmid = int(vm_id)
        node = self._node_for_vm(vmid)
        return ProxmoxVM(vmid, node, self._backend)

    def find_vm(self, name: str) -> ProxmoxVM:
        """Return a ProxmoxVM by name. Raises VmNotFoundError if not found."""
        for vm in self._all_vms():
            if vm.get("name") == name:
                return ProxmoxVM(
                    int(vm["vmid"]), vm["node"], self._backend
                )
        raise VmNotFoundError(name)

    def list(self, node: str | None = None) -> List[VmInfo]:
        """Return all VMs (optionally filtered to a node)."""
        vms = self._all_vms(node=node)
        return [VmInfo.from_api(v) for v in vms]

    def list_nodes(self) -> List[NodeInfo]:
        """Return all nodes in the cluster."""
        raw = self._backend.get("nodes")
        return [NodeInfo.from_api(n) for n in raw]

    def list_templates(self, node: str | None = None) -> List[TemplateInfo]:
        """Return VMs flagged as templates."""
        vms = self._all_vms(node=node)
        return [
            TemplateInfo.from_api(v)
            for v in vms
            if v.get("template")
        ]

    def find_template(self, name: str) -> TemplateInfo:
        """Find a template by name. Raises VmNotFoundError if not found."""
        for t in self.list_templates():
            if t.name == name:
                return t
        raise VmNotFoundError(name)

    # ------------------------------------------------------------------
    # VM creation / cleanup
    # ------------------------------------------------------------------

    def create_vm(
        self,
        name: str,
        template_id: int,
        node: str | None = None,
        *,
        cores: int | None = None,
        memory_mb: int | None = None,
        disk_gb: int | None = None,
        cloud_init_config: CloudInitConfig | None = None,
        start: bool = True,
    ) -> ProxmoxVM:
        """
        Clone a template VM, optionally apply cloud-init, and start it.

        Cloud-init (username, password, SSH keys, IP config) is applied
        after the clone and before the VM is started::

            vm = client.create_vm(
                "node-1",
                template_id=9000,
                cloud_init_config=CloudInitConfig(
                    username="ubuntu",
                    ssh_keys=["ssh-rsa AAAA..."],
                    ip_config="ip=dhcp",
                ),
            )

        Returns the new ProxmoxVM instance.
        """
        target_node = node or self._default_node()
        new_vmid = self._next_vmid()

        upid = self._backend.post(
            f"nodes/{target_node}/qemu/{template_id}/clone",
            newid=new_vmid,
            name=name,
            target=target_node,
            full=1,
        )
        self._backend.wait_for_task(target_node, upid)

        vm = ProxmoxVM(new_vmid, target_node, self._backend)

        hw_params: dict[str, Any] = {}
        if cores is not None:
            hw_params["cores"] = cores
        if memory_mb is not None:
            hw_params["memory"] = memory_mb
        if hw_params:
            self._backend.put(f"nodes/{target_node}/qemu/{new_vmid}/config", **hw_params)
        if disk_gb is not None:
            vm.resize_disk("scsi0", f"{disk_gb}G")

        if cloud_init_config is not None:
            vm.configure_cloud_init(cloud_init_config)

        if start:
            vm.start()

        return vm

    def purge_stopped(self, node: str | None = None) -> None:
        """Delete all stopped VMs (use with care)."""
        for vm_info in self.list(node=node):
            if vm_info.state.value == "stopped":
                pvm = ProxmoxVM(vm_info.vm_id, vm_info.node, self._backend)
                pvm.delete(purge=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_vms(self, node: str | None = None) -> List[dict[str, Any]]:
        resources = self._backend.get("cluster/resources", type="vm")
        if node:
            return [r for r in resources if r.get("node") == node]
        if self._node:
            return [r for r in resources if r.get("node") == self._node]
        return list(resources)

    def _node_for_vm(self, vmid: int) -> str:
        """Find which node a VM is on. Raises VmNotFoundError if absent."""
        resources = self._backend.get("cluster/resources", type="vm")
        for entry in resources:
            if int(entry.get("vmid", -1)) == vmid:
                return str(entry["node"])
        raise VmNotFoundError(vmid)

    def _default_node(self) -> str:
        if self._node:
            return self._node
        nodes = self._backend.get("nodes")
        if nodes:
            return str(nodes[0]["node"])
        raise RuntimeError("No nodes available in the cluster")

    def _next_vmid(self) -> int:
        """Return the next available VMID (simple heuristic)."""
        try:
            result = self._backend.get("cluster/nextid")
            return int(result)
        except Exception:
            existing = {
                int(v.get("vmid", 0))
                for v in self._backend.get("cluster/resources", type="vm")
            }
            return max(existing, default=99) + 1

    @staticmethod
    def _build_backend(
        host: str,
        user: str,
        password: str | None,
        token_name: str | None,
        token_value: str | None,
        port: int,
        verify_ssl: bool,
    ) -> ProxmoxBackend:
        try:
            from proxmoxer import ProxmoxAPI
        except ImportError as exc:
            raise ImportError(
                "proxmoxer is required for the real backend. "
                "Install it with: pip install proxmoxer requests"
            ) from exc

        from proxmox_sdk.backends.proxmoxer import ProxmoxerBackend

        if token_name and token_value:
            api = ProxmoxAPI(
                host,
                user=user,
                token_name=token_name,
                token_value=token_value,
                verify_ssl=verify_ssl,
                port=port,
            )
        else:
            api = ProxmoxAPI(
                host,
                user=user,
                password=password or "",
                verify_ssl=verify_ssl,
                port=port,
            )

        return ProxmoxerBackend(api)

    def __repr__(self) -> str:
        return f"ProxmoxClient(host={self._host!r}, user={self._user!r})"
