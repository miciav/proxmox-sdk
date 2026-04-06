from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SshBackend(Protocol):
    """
    Abstracts SSH command execution on a remote host.

    Used by ProxmoxRoutingManager to run commands on the Proxmox host.
    Implementations: ParamikoSshBackend (real), FakeSshBackend (tests).
    """

    def run(self, command: str) -> tuple[int, str, str]:
        """
        Execute a command on the remote host.

        Returns (exit_code, stdout, stderr).
        """
        ...

    def read_file(self, path: str) -> str:
        """Read a remote file and return its contents."""
        ...

    def write_file(self, path: str, content: str) -> None:
        """Write content to a remote file (atomic via tmp file)."""
        ...


class ParamikoSshBackend:
    """Real SSH backend using paramiko."""

    def __init__(
        self,
        host: str,
        user: str,
        ssh_key_path: str | None = None,
        password: str | None = None,
        port: int = 22,
    ) -> None:
        try:
            import paramiko
        except ImportError as exc:
            raise ImportError(
                "paramiko is required for SSH operations. "
                "Install it with: pip install proxmox-sdk[ssh]"
            ) from exc

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {
            "hostname": host,
            "username": user,
            "port": port,
        }
        if ssh_key_path:
            connect_kwargs["key_filename"] = ssh_key_path
        if password:
            connect_kwargs["password"] = password
        self._client.connect(**connect_kwargs)

    def run(self, command: str) -> tuple[int, str, str]:
        _, stdout, stderr = self._client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, stdout.read().decode(), stderr.read().decode()

    def read_file(self, path: str) -> str:
        _, stdout, _ = self._client.exec_command(f"cat {path}")
        stdout.channel.recv_exit_status()
        return stdout.read().decode()

    def write_file(self, path: str, content: str) -> None:
        # Write atomically via a tmp file
        tmp = f"{path}.proxmox_sdk_tmp"
        sftp = self._client.open_sftp()
        with sftp.file(tmp, "w") as f:
            f.write(content)
        sftp.close()
        self.run(f"mv {tmp} {path}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ParamikoSshBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class FakeSshBackend:
    """
    In-memory SSH backend for unit testing.

    Simulates a Proxmox host's filesystem and command output without
    any real network connection.
    """

    def __init__(self) -> None:
        # filename -> content
        self._files: dict[str, str] = {}
        # command prefix -> (exit_code, stdout, stderr)
        self._responses: dict[str, tuple[int, str, str]] = {}
        self.commands: list[str] = []

    def seed_file(self, path: str, content: str) -> None:
        """Pre-populate a file on the fake filesystem."""
        self._files[path] = content

    def seed_response(
        self, command_prefix: str, exit_code: int, stdout: str, stderr: str = ""
    ) -> None:
        """Register a canned response for commands starting with command_prefix."""
        self._responses[command_prefix] = (exit_code, stdout, stderr)

    def run(self, command: str) -> tuple[int, str, str]:
        self.commands.append(command)
        for prefix, response in self._responses.items():
            if command.startswith(prefix):
                return response
        # Default: success, no output
        return 0, "", ""

    def read_file(self, path: str) -> str:
        return self._files.get(path, "")

    def write_file(self, path: str, content: str) -> None:
        self._files[path] = content

    def assert_ran(self, substring: str) -> None:
        """Assert that a command containing substring was executed."""
        for cmd in self.commands:
            if substring in cmd:
                return
        raise AssertionError(
            f"Expected a command containing {substring!r}. "
            f"Ran: {self.commands}"
        )
