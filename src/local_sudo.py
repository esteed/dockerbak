"""
Local sudo operations for backup file handling.
"""

import subprocess
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger('dockerbak.sudo')


class LocalSudoHelper:
    """Helper for executing local commands with sudo when needed."""

    def __init__(self, use_sudo: bool = False):
        """
        Initialize local sudo helper.

        Args:
            use_sudo: Whether to use sudo for local file operations
        """
        self.use_sudo = use_sudo

    def mkdir(self, path: Path, mode: int = 0o755, parents: bool = True) -> bool:
        """
        Create directory with optional sudo.

        Args:
            path: Directory path to create
            mode: Directory permissions
            parents: Create parent directories if needed

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"mkdir: path={path}, use_sudo={self.use_sudo}, parents={parents}")

            if self.use_sudo:
                # Use sudo to create directory - don't change ownership, just run as root
                cmd = ['sudo', 'mkdir']
                if parents:
                    cmd.append('-p')
                cmd.append(str(path))

                logger.debug(f"mkdir: executing {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"mkdir failed: returncode={result.returncode}, stderr={result.stderr}")
                    raise RuntimeError(f"Failed to create directory: {result.stderr}")

                logger.debug(f"mkdir: successfully created {path}")
                return True
            else:
                logger.debug(f"mkdir: creating without sudo")
                path.mkdir(mode=mode, parents=parents, exist_ok=True)
                logger.debug(f"mkdir: successfully created {path}")
                return True

        except Exception as e:
            logger.error(f"mkdir exception: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create directory {path}: {str(e)}")

    def is_writable(self, path: Path) -> bool:
        """
        Check if path is writable.

        Args:
            path: Path to check

        Returns:
            True if writable, False otherwise
        """
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                # Check parent directory - walk up until we find one that exists
                parent = path.parent
                while parent != parent.parent:  # Stop at root
                    try:
                        if parent.exists():
                            return os.access(parent, os.W_OK)
                        parent = parent.parent
                    except (PermissionError, OSError):
                        # Can't check this parent, try the next one up
                        parent = parent.parent
                        continue
                return False
        except (PermissionError, OSError):
            # If we get permission error checking, assume not writable
            return False

    def needs_sudo(self, path: Path) -> bool:
        """
        Check if sudo is needed to write to path.

        Args:
            path: Path to check

        Returns:
            True if sudo is needed, False otherwise
        """
        try:
            # If path starts with /backups, /opt, /usr, /etc, etc., assume sudo needed
            path_str = str(path)
            if path_str.startswith(('/backups', '/opt', '/usr', '/etc', '/var', '/srv')):
                return True

            return not self.is_writable(path)
        except Exception:
            # If anything goes wrong checking, assume sudo needed for safety
            return True

    def write_file(self, path: Path, content: str) -> bool:
        """
        Write content to file with optional sudo.

        Args:
            path: File path to write
            content: Content to write

        Returns:
            True if successful
        """
        try:
            logger.debug(f"write_file: path={path}, use_sudo={self.use_sudo}, content_length={len(content)}")

            if self.use_sudo:
                # Write to temp file, then use sudo to move it
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                logger.debug(f"write_file: wrote to temp {tmp_path}, moving with sudo")
                # Use sudo to move file - no ownership change, run as root
                subprocess.run(['sudo', 'mv', tmp_path, str(path)], check=True)
                logger.debug(f"write_file: successfully moved to {path}")
                return True
            else:
                logger.debug(f"write_file: writing without sudo")
                path.write_text(content)
                logger.debug(f"write_file: successfully wrote {path}")
                return True
        except Exception as e:
            logger.error(f"write_file exception: {e}", exc_info=True)
            raise RuntimeError(f"Failed to write file {path}: {str(e)}")

    def write_json(self, path: Path, data: dict, indent: int = 2) -> bool:
        """
        Write JSON data to file with optional sudo.

        Args:
            path: File path to write
            data: Dictionary to write as JSON
            indent: JSON indentation

        Returns:
            True if successful
        """
        import json
        content = json.dumps(data, indent=indent)
        return self.write_file(path, content)

    def read_file(self, path: Path) -> str:
        """
        Read file content with optional sudo.

        Args:
            path: File path to read

        Returns:
            File content as string
        """
        try:
            if self.use_sudo:
                result = subprocess.run(
                    ['sudo', 'cat', str(path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout
            else:
                return path.read_text()
        except Exception as e:
            raise RuntimeError(f"Failed to read file {path}: {str(e)}")

    def read_json(self, path: Path) -> dict:
        """
        Read JSON file with optional sudo.

        Args:
            path: File path to read

        Returns:
            Parsed JSON as dictionary
        """
        import json
        content = self.read_file(path)
        return json.loads(content)

    def read_binary(self, path: Path) -> bytes:
        """
        Read binary file with optional sudo.

        Args:
            path: File path to read

        Returns:
            File content as bytes
        """
        try:
            if self.use_sudo:
                result = subprocess.run(
                    ['sudo', 'cat', str(path)],
                    capture_output=True,
                    check=True
                )
                return result.stdout
            else:
                return path.read_bytes()
        except Exception as e:
            raise RuntimeError(f"Failed to read binary file {path}: {str(e)}")
