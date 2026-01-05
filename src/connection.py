"""
SSH connection management for remote Docker hosts.
"""

from typing import Optional, Tuple
import paramiko
from pathlib import Path
import io


class SSHConnection:
    """Manages SSH connection to remote Docker host."""

    def __init__(self):
        """Initialize SSH connection manager."""
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.host: Optional[str] = None

    def connect(self, host: str, username: str,
                password: Optional[str] = None,
                ssh_key_path: Optional[str] = None,
                port: int = 22) -> bool:
        """
        Establish SSH connection to remote host.

        Args:
            host: Hostname or IP address
            username: SSH username
            password: SSH password (if not using key)
            ssh_key_path: Path to SSH private key (if not using password)
            port: SSH port (default: 22)

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username,
            }

            if ssh_key_path:
                connect_kwargs["key_filename"] = ssh_key_path
            elif password:
                connect_kwargs["password"] = password
            else:
                raise ValueError("Either password or ssh_key_path must be provided")

            self.client.connect(**connect_kwargs)
            self.sftp = self.client.open_sftp()
            self.host = host
            return True

        except Exception as e:
            if self.client:
                self.client.close()
            self.client = None
            self.sftp = None
            raise ConnectionError(f"Failed to connect to {host}: {str(e)}")

    def execute_command(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """
        Execute command on remote host.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        if not self.client:
            raise RuntimeError("Not connected to remote host")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()

            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')

            return stdout_text, stderr_text, exit_code

        except Exception as e:
            raise RuntimeError(f"Command execution failed: {str(e)}")

    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Download file from remote host via SFTP.

        Args:
            remote_path: Path to file on remote host
            local_path: Local destination path
        """
        if not self.sftp:
            raise RuntimeError("SFTP not available")

        try:
            # Ensure local directory exists (only if it doesn't already exist)
            parent_dir = Path(local_path).parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except (PermissionError, OSError):
                    # Parent directory might need sudo - should be pre-created by caller
                    # If it doesn't exist and we can't create it, let the error propagate
                    pass
            self.sftp.get(remote_path, local_path)
        except Exception as e:
            raise RuntimeError(f"File download failed: {str(e)}")

    def download_directory(self, remote_path: str, local_path: str) -> None:
        """
        Recursively download directory from remote host.

        Args:
            remote_path: Path to directory on remote host
            local_path: Local destination path
        """
        if not self.sftp:
            raise RuntimeError("SFTP not available")

        try:
            local_dir = Path(local_path)
            if not local_dir.exists():
                try:
                    local_dir.mkdir(parents=True, exist_ok=True)
                except (PermissionError, OSError):
                    # Directory might need sudo - should be pre-created by caller
                    pass

            for item in self.sftp.listdir_attr(remote_path):
                remote_item = f"{remote_path}/{item.filename}"
                local_item = local_dir / item.filename

                if self._is_directory(item):
                    self.download_directory(remote_item, str(local_item))
                else:
                    self.sftp.get(remote_item, str(local_item))

        except Exception as e:
            raise RuntimeError(f"Directory download failed: {str(e)}")

    def _is_directory(self, attr) -> bool:
        """Check if SFTP attribute represents a directory."""
        import stat
        return stat.S_ISDIR(attr.st_mode)

    def read_file(self, remote_path: str) -> str:
        """
        Read file content from remote host.

        Args:
            remote_path: Path to file on remote host

        Returns:
            File content as string
        """
        if not self.sftp:
            raise RuntimeError("SFTP not available")

        try:
            with self.sftp.file(remote_path, 'r') as f:
                return f.read().decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"File read failed: {str(e)}")

    def file_exists(self, remote_path: str) -> bool:
        """
        Check if file exists on remote host.

        Args:
            remote_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        if not self.sftp:
            raise RuntimeError("SFTP not available")

        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def create_temp_file(self, content: str) -> str:
        """
        Create temporary file on remote host with given content.

        Args:
            content: File content

        Returns:
            Path to temporary file on remote host
        """
        if not self.client:
            raise RuntimeError("Not connected to remote host")

        # Create temp file path
        stdout, _, _ = self.execute_command("mktemp")
        temp_path = stdout.strip()

        # Write content to temp file
        if self.sftp:
            with self.sftp.file(temp_path, 'w') as f:
                f.write(content)

        return temp_path

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.sftp:
            self.sftp.close()
            self.sftp = None

        if self.client:
            self.client.close()
            self.client = None

        self.host = None

    def is_connected(self) -> bool:
        """
        Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        if not self.client:
            return False

        try:
            transport = self.client.get_transport()
            return transport and transport.is_active()
        except Exception:
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
