"""End-to-end verification: create VM(s), verify readiness, delete VM(s).

Prerequisites:
    PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD env vars set
    PROXMOX_NODE env var (or --node)

Usage:
    uv run proxmox-vm-e2e --node pve --template-id 9000
    uv run proxmox-vm-e2e --name test-vm --template-id 9000 --cores 2 --memory-mb 2048
    uv run proxmox-vm-e2e --count 3 --template-id 9000
    uv run proxmox-vm-e2e --configs '[{"name":"web","template_id":9000,"cores":2}]'
    uv run proxmox-vm-e2e --list-templates
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .client import ProxmoxClient
from .exceptions import ProxmoxError
from .models import VmConfig
from .vm import ProxmoxVM


def _env_or_raise(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _verify_vm(vm: ProxmoxVM, idx: int, total: int, timeout: float) -> int:
    label = f"  [{idx}/{total}] {vm.vm_id}"
    exit_code = 0

    print(f"{label}: waiting for guest agent ...")
    t0 = time.monotonic()
    try:
        vm.wait_for_agent(timeout=timeout)
    except ProxmoxError as exc:
        print(f"{label}: agent timeout — {exc}", file=sys.stderr)
        return 1
    print(f"{label}: agent ready in {time.monotonic() - t0:.1f}s")

    print(f"{label}: waiting for IP ...")
    t0 = time.monotonic()
    try:
        ip = vm.wait_for_ip(timeout=timeout)
    except ProxmoxError as exc:
        print(f"{label}: IP timeout — {exc}", file=sys.stderr)
        return 1
    print(f"{label}: got IP {ip} in {time.monotonic() - t0:.1f}s")

    print(f"{label}: running verification command ...")
    result = vm.exec(["hostname"])
    print(f"{label}: exit={result.exit_code}  stdout={result.stdout.strip()}")
    if result.stderr:
        print(f"{label}: stderr={result.stderr.strip()}")
    if not result.success:
        print(f"{label}: FAILED", file=sys.stderr)
        exit_code = 1

    info = vm.info()
    print(f"{label}: state={info.state.value}  node={info.node}  "
          f"cores={info.cpu_count}  mem={info.memory_mb}MB")
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end Proxmox VM lifecycle test (create, verify, delete)."
    )
    parser.add_argument("--name", default=None, help="VM name prefix.")
    parser.add_argument("--template-id", type=int, default=None, help="Template VMID to clone.")
    parser.add_argument("--node", default=None, help="Proxmox node (default: PROXMOX_NODE env).")
    parser.add_argument("--cores", type=int, default=None)
    parser.add_argument("--memory-mb", type=int, default=None)
    parser.add_argument("--disk-gb", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=300, help="Max wait seconds.")
    parser.add_argument("--count", type=int, default=1, help="Number of VMs.")
    parser.add_argument(
        "--configs", default=None,
        help="JSON array of VmConfig objects. Mutually exclusive with --count.",
    )
    parser.add_argument("--list-templates", action="store_true", help="List templates and exit.")
    args = parser.parse_args()

    if args.configs and args.count != 1:
        raise SystemExit("--configs and --count are mutually exclusive")
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    host = _env_or_raise("PROXMOX_HOST")
    user = _env_or_raise("PROXMOX_USER")
    password = os.environ.get("PROXMOX_PASSWORD")
    token_name = os.environ.get("PROXMOX_TOKEN_NAME")
    token_value = os.environ.get("PROXMOX_TOKEN_VALUE")
    node = args.node or os.environ.get("PROXMOX_NODE")

    client = ProxmoxClient(
        host=host, user=user, password=password,
        token_name=token_name, token_value=token_value,
        node=node, verify_ssl=False,
    )

    if args.list_templates:
        templates = client.list_templates()
        print(f"{'VMID':>6}  {'Name':<30}  {'Node':<10}  {'Cores':>6}  {'Memory':>10}")
        print("-" * 75)
        for t in templates:
            print(f"{t.vm_id:>6}  {t.name:<30}  {t.node:<10}  {t.cores:>6}  {t.memory_mb:>8}MB")
        raise SystemExit(0)

    if args.configs:
        try:
            raw = json.loads(args.configs)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--configs: invalid JSON — {exc}") from exc
        if not isinstance(raw, list) or not raw:
            raise SystemExit("--configs: expected a non-empty JSON array")
        configs = [VmConfig(**item) for item in raw]
    else:
        if not args.template_id:
            raise SystemExit("--template-id is required (or use --configs)")
        prefix = args.name or f"e2e-{int(time.time())}"
        if args.count == 1:
            configs = [
                VmConfig(name=prefix, template_id=args.template_id, node=node,
                         cores=args.cores, memory_mb=args.memory_mb,
                         disk_gb=args.disk_gb)
            ]
        else:
            configs = [
                VmConfig(name=f"{prefix}-{i}", template_id=args.template_id,
                         node=node, cores=args.cores, memory_mb=args.memory_mb,
                         disk_gb=args.disk_gb)
                for i in range(args.count)
            ]

    n = len(configs)
    vms: list[ProxmoxVM] = []
    exit_code = 0

    try:
        if n == 1:
            print(f"[1/3] Launching VM '{configs[0].name}' ...")
        else:
            print(f"[1/3] Launching {n} VMs in parallel ...")
            for cfg in configs:
                print(f"       - {cfg.name}")
        t0 = time.monotonic()
        vms = client.launch_many(configs)
        dt = time.monotonic() - t0
        print(f"       {'launch' if n == 1 else f'all {n} launches'} completed in {dt:.1f}s")

        print(f"[2/3] Verifying {n} VM(s) ...")
        for i, vm in enumerate(vms, start=1):
            rc = _verify_vm(vm, i, n, args.timeout)
            if rc != 0:
                exit_code = 1

    except ProxmoxError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        exit_code = 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        exit_code = 130

    if vms:
        if n == 1:
            print(f"[3/3] Deleting VM '{vms[0].vm_id}' ...")
        else:
            print(f"[3/3] Deleting {len(vms)} VM(s) ...")
        try:
            for vm in vms:
                vm.delete(purge=True)
            print("       done.")
        except ProxmoxError as exc:
            print(f"       cleanup failed: {exc}", file=sys.stderr)
            exit_code = 3

    print()
    if exit_code == 0:
        print(f"SUCCESS — {n} VM(s) completed full lifecycle.")
    else:
        print(f"FAILURE (exit code {exit_code})")

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
