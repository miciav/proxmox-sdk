# proxmox-sdk

Python SDK per la gestione di VM Proxmox VE. Fornisce un'API ad alto livello sopra la REST API di Proxmox, con supporto per il testing tramite backend in-memory.

## Installazione

```bash
pip install proxmox-sdk
# oppure con uv
uv add proxmox-sdk
```

Richiede `proxmoxer` e `requests` per il backend reale:

```bash
pip install proxmoxer requests
```

## Connessione

```python
from proxmox_sdk import ProxmoxClient

# Con password
client = ProxmoxClient(
    host="192.168.1.100",
    user="root@pam",
    password="secret",
    node="pve",          # nodo di default (opzionale)
    verify_ssl=False,
)

# Con API token
client = ProxmoxClient(
    host="192.168.1.100",
    user="root@pam",
    token_name="mytoken",
    token_value="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
)

# Da URL completo
client = ProxmoxClient.from_url(
    "https://192.168.1.100:8006/api2/json",
    user="root@pam",
    password="secret",
)
```

---

## ProxmoxClient — metodi disponibili

### Query VM

```python
# Lista tutte le VM
vms: list[VmInfo] = client.list()
vms = client.list(node="pve")   # filtrate per nodo

# Recupera una VM per ID
vm: ProxmoxVM = client.get_vm(100)

# Cerca una VM per nome
vm = client.find_vm("node-1")   # lancia VmNotFoundError se assente
```

### Template

```python
# Lista tutti i template con info hardware
templates: list[TemplateInfo] = client.list_templates()
templates = client.list_templates(node="pve")

# Cerca un template per nome
t: TemplateInfo = client.find_template("ubuntu-22.04")
# t.vm_id, t.name, t.node, t.cores, t.memory_mb, t.description

# Lancia VmNotFoundError se non trovato
```

### Creazione VM

```python
from proxmox_sdk import CloudInitConfig

vm = client.create_vm(
    "node-1",
    template_id=9000,       # VMID del template da clonare (full clone)
    node="pve",             # nodo di destinazione (default: primo disponibile)
    cores=4,                # None = eredita dal template
    memory_mb=4096,         # None = eredita dal template
    disk_gb=50,             # None = eredita dal template
    cloud_init_config=CloudInitConfig(
        username="ubuntu",
        password="secret",
        ssh_keys=["ssh-rsa AAAA..."],
        ip_config="ip=dhcp",
        # ip_config="ip=10.0.0.5/24,gw=10.0.0.1"  # IP statico
        nameserver="8.8.8.8",
        searchdomain="home.local",
    ),
    start=True,             # avvia la VM dopo la configurazione (default: True)
)
# Ordine garantito: clone → hw config → cloud-init → start
```

### Cleanup

```python
# Elimina tutte le VM ferme (usa con cautela)
client.purge_stopped()
client.purge_stopped(node="pve")
```

### Nodi

```python
nodes: list[NodeInfo] = client.list_nodes()
# n.name, n.status, n.cpu_count, n.memory_total_bytes, n.memory_used_bytes, n.uptime_seconds
```

---

## ProxmoxVM — metodi disponibili

Restituito da `get_vm()`, `find_vm()`, `create_vm()`.

### Stato e metriche

```python
info: VmInfo = vm.info()
# info.vm_id, info.name, info.node, info.state (VmState), info.cpu_count,
# info.memory_mb, info.uptime_seconds, info.tags

metrics: VmMetrics = vm.metrics()
# metrics.cpu_pct, metrics.mem_used_bytes, metrics.mem_total_bytes,
# metrics.net_in_bytes, metrics.net_out_bytes, metrics.disk_read_bytes
```

### Ciclo di vita

```python
vm.start()
vm.stop()                  # hard stop immediato
vm.stop(force=True)        # forza l'arresto
vm.shutdown()              # ACPI graceful shutdown
vm.restart()
vm.delete()
vm.delete(purge=True)      # rimuove anche dai job config
```

### Attesa

```python
vm.wait_for_agent(timeout=120)   # aspetta che il guest agent risponda
vm.wait_for_ip(timeout=120)      # aspetta un indirizzo IPv4 dal guest agent
vm.wait_ready(timeout=120)       # aspetta running + guest agent attivo
```

### Snapshot

```python
snap: SnapshotInfo = vm.snapshot("pre-upgrade", description="Prima dell'aggiornamento")
vm.restore("pre-upgrade")        # rollback allo snapshot
snaps: list[SnapshotInfo] = vm.list_snapshots()
```

### Clone

```python
new_vm: ProxmoxVM = vm.clone(new_vm_id=200, name="node-2", full=True)
```

### Disk

```python
vm.resize_disk("scsi0", "50G")    # dimensione assoluta
vm.resize_disk("scsi0", "+10G")   # incremento relativo
```

### Cloud-init (post-clone)

```python
vm.configure_cloud_init(CloudInitConfig(
    username="ubuntu",
    ssh_keys=["ssh-rsa AAAA..."],
    ip_config="ip=dhcp",
))
```

### Esecuzione comandi (guest agent)

```python
result: CommandResult = vm.exec(["hostname"])
result.exit_code   # int
result.stdout      # str
result.stderr      # str
result.success     # bool
```

---

## NAT / Port Forwarding — ProxmoxRoutingManager

Gestisce regole iptables DNAT sull'host Proxmox tramite SSH. Equivalente agli Ansible playbook `add_nat_rules.yml` / `remove_nat_rules.yml`.

```python
from proxmox_sdk import ProxmoxRoutingManager, PortMapping

# Connessione SSH all'host Proxmox
mgr = ProxmoxRoutingManager.from_key(
    host="192.168.1.100",
    user="root",
    ssh_key_path="~/.ssh/id_rsa",
)
# oppure con password:
mgr = ProxmoxRoutingManager.from_password(
    host="192.168.1.100",
    user="root",
    password="secret",
)

# Aggiunge regole (le porte host vengono assegnate automaticamente)
mappings = [
    PortMapping(vm_id=100, vm_name="node-1", vm_ip="10.0.0.10", vm_port=22, service="SSH"),
    PortMapping(vm_id=100, vm_name="node-1", vm_ip="10.0.0.10", vm_port=6443, service="k3s"),
]
assigned: list[PortMapping] = mgr.add_rules(mappings)
for m in assigned:
    print(f"{m.service}: host:{m.host_port} -> {m.vm_ip}:{m.vm_port}")

# Lista le regole attive
rules: list[PortMapping] = mgr.list_rules()

# Rimuove regole specifiche
mgr.remove_rules(assigned)

# Rimuove tutte le regole gestite dalla libreria
mgr.flush_rules()
```

Le porte host vengono scelte automaticamente evitando quelle già in uso (rilevate via `ss -tln`).

---

## Modelli dati

| Classe | Campi principali |
|---|---|
| `VmInfo` | `vm_id`, `name`, `node`, `state` (VmState), `cpu_count`, `memory_mb`, `uptime_seconds`, `tags`, `template` |
| `VmMetrics` | `vm_id`, `cpu_pct`, `mem_used_bytes`, `mem_total_bytes`, `net_in_bytes`, `net_out_bytes` |
| `VmState` | enum: `RUNNING`, `STOPPED`, `PAUSED`, `SUSPENDED`, `UNKNOWN` |
| `TemplateInfo` | `vm_id`, `name`, `node`, `cores`, `memory_mb`, `description` |
| `NodeInfo` | `name`, `status`, `cpu_count`, `memory_total_bytes`, `memory_used_bytes`, `uptime_seconds` |
| `SnapshotInfo` | `name`, `vm_id`, `created`, `description`, `parent` |
| `CloudInitConfig` | `username`, `password`, `ssh_keys`, `ip_config`, `nameserver`, `searchdomain` |
| `CommandResult` | `exit_code`, `stdout`, `stderr`, `success` |
| `PortMapping` | `vm_id`, `vm_name`, `vm_ip`, `vm_port`, `host_port`, `service` |

---

## Eccezioni

Tutte derivano da `ProxmoxError`.

| Eccezione | Quando |
|---|---|
| `ProxmoxAuthError` | Autenticazione fallita |
| `ProxmoxConnectionError` | Host non raggiungibile |
| `ProxmoxAPIError` | La REST API restituisce un errore |
| `VmNotFoundError` | VM o template non trovato per ID o nome |
| `VmStateError` | Operazione non valida per lo stato attuale della VM |
| `NodeNotFoundError` | Nodo non trovato nel cluster |
| `ProxmoxTimeoutError` | Un'operazione di attesa ha superato il timeout |
| `SnapshotNotFoundError` | Snapshot non trovato sulla VM |
| `TaskFailedError` | Un task asincrono Proxmox è terminato con errore |

---

## Testing con FakeBackend

Tutti i test della libreria usano `FakeBackend` — uno state machine in-memory che non richiede un server Proxmox reale.

```python
from proxmox_sdk import ProxmoxClient, FakeBackend

fb = FakeBackend()
fb.add_vm(9000, node="pve", name="ubuntu-22.04", status="stopped", template=True)
fb.add_vm(100,  node="pve", name="node-1", status="running")

client = ProxmoxClient(host="x", user="x", node="pve", backend=fb)

# Usa il client normalmente nei test
vm = client.create_vm("test-vm", template_id=9000, cores=2, start=False)
assert vm.vm_id is not None

# Ispezione diretta dello stato interno
fb.assert_called_with("PUT", f"nodes/pve/qemu/{vm.vm_id}/config")
stored = fb.get(f"nodes/pve/qemu/{vm.vm_id}/config")
assert stored["cores"] == 2
```

Per il testing SSH (routing NAT) usa `FakeSshBackend`:

```python
from proxmox_sdk import FakeSshBackend, ProxmoxRoutingManager

ssh = FakeSshBackend()
ssh.seed_file("/etc/network/interfaces", "auto lo\niface lo inet loopback\n")
ssh.seed_response("ss -tln", (0, "Netid  State  Recv-Q  Send-Q  Local Address:Port\n", ""))

mgr = ProxmoxRoutingManager(ssh_backend=ssh, interface="eth0")
```
