"""
Secure credential management with master password encryption.
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet


class CredentialManager:
    """Manages encrypted storage of SSH credentials."""

    DOCKERBAK_DIR = Path.home() / ".dockerbak"
    CREDENTIALS_FILE = DOCKERBAK_DIR / "credentials.enc"
    SALT_FILE = DOCKERBAK_DIR / "salt"
    ITERATIONS = 600000  # High iteration count for security

    def __init__(self):
        """Initialize credential manager and ensure storage directory exists."""
        self.DOCKERBAK_DIR.mkdir(mode=0o700, exist_ok=True)
        self._fernet: Optional[Fernet] = None

    def _derive_key(self, master_password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from master password using PBKDF2.

        Args:
            master_password: The master password
            salt: Salt for key derivation

        Returns:
            32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return key

    def _get_or_create_salt(self) -> bytes:
        """
        Get existing salt or create new one.

        Returns:
            16-byte salt
        """
        if self.SALT_FILE.exists():
            return self.SALT_FILE.read_bytes()
        else:
            salt = os.urandom(16)
            self.SALT_FILE.write_bytes(salt)
            self.SALT_FILE.chmod(0o600)
            return salt

    def unlock(self, master_password: str) -> bool:
        """
        Unlock credential store with master password.

        Args:
            master_password: The master password

        Returns:
            True if unlock successful, False otherwise
        """
        try:
            salt = self._get_or_create_salt()
            key = self._derive_key(master_password, salt)
            self._fernet = Fernet(key)

            # Test decryption if credentials exist
            if self.CREDENTIALS_FILE.exists():
                self._decrypt_credentials()

            return True
        except Exception:
            self._fernet = None
            return False

    def _encrypt_credentials(self, credentials: Dict) -> bytes:
        """Encrypt credentials dictionary."""
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        json_data = json.dumps(credentials).encode()
        return self._fernet.encrypt(json_data)

    def _decrypt_credentials(self) -> Dict:
        """Decrypt credentials from file."""
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        if not self.CREDENTIALS_FILE.exists():
            return {}

        encrypted_data = self.CREDENTIALS_FILE.read_bytes()
        decrypted_data = self._fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data)

    def save_credentials(self, host: str, username: str,
                        password: Optional[str] = None,
                        ssh_key_path: Optional[str] = None,
                        port: int = 22,
                        vanity_name: Optional[str] = None) -> None:
        """
        Save SSH credentials for a host.

        Args:
            host: Hostname or IP address
            username: SSH username
            password: SSH password (optional)
            ssh_key_path: Path to SSH private key (optional)
            port: SSH port (default: 22)
            vanity_name: Optional display name for the host
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()

        # Preserve existing vanity name if not provided
        existing_vanity = None
        if host in credentials:
            existing_vanity = credentials[host].get('vanity_name')

        credentials[host] = {
            "username": username,
            "password": password,
            "ssh_key_path": ssh_key_path,
            "port": port,
            "vanity_name": vanity_name if vanity_name is not None else existing_vanity
        }

        encrypted = self._encrypt_credentials(credentials)
        self.CREDENTIALS_FILE.write_bytes(encrypted)
        self.CREDENTIALS_FILE.chmod(0o600)

    def load_credentials(self, host: str) -> Optional[Dict]:
        """
        Load credentials for a specific host.

        Args:
            host: Hostname to retrieve credentials for

        Returns:
            Dictionary with credentials or None if not found
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()
        return credentials.get(host)

    def list_hosts(self) -> list:
        """
        List all hosts with stored credentials.

        Returns:
            List of hostnames
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()
        return list(credentials.keys())

    def delete_credentials(self, host: str) -> bool:
        """
        Delete credentials for a host.

        Args:
            host: Hostname to delete credentials for

        Returns:
            True if deleted, False if not found
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()

        if host in credentials:
            del credentials[host]
            encrypted = self._encrypt_credentials(credentials)
            self.CREDENTIALS_FILE.write_bytes(encrypted)
            return True

        return False

    def has_stored_credentials(self) -> bool:
        """
        Check if any credentials are stored.

        Returns:
            True if credentials file exists and is not empty
        """
        return self.CREDENTIALS_FILE.exists() and self.CREDENTIALS_FILE.stat().st_size > 0

    def set_vanity_name(self, host: str, vanity_name: str) -> bool:
        """
        Set or update vanity name for a host.

        Args:
            host: Hostname or IP address
            vanity_name: Display name for the host

        Returns:
            True if updated, False if host not found
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()

        if host in credentials:
            credentials[host]['vanity_name'] = vanity_name
            encrypted = self._encrypt_credentials(credentials)
            self.CREDENTIALS_FILE.write_bytes(encrypted)
            return True

        return False

    def get_display_name(self, host: str) -> str:
        """
        Get display name for a host (vanity name if set, otherwise hostname).

        Args:
            host: Hostname or IP address

        Returns:
            Display name for the host
        """
        if not self._fernet:
            return host

        credentials = self._decrypt_credentials()
        if host in credentials:
            vanity = credentials[host].get('vanity_name')
            if vanity:
                return f"{vanity} ({host})"

        return host

    def list_hosts_with_names(self) -> Dict[str, str]:
        """
        List all hosts with their display names.

        Returns:
            Dictionary mapping host to display name
        """
        if not self._fernet:
            raise RuntimeError("Credential store not unlocked")

        credentials = self._decrypt_credentials()
        result = {}

        for host, creds in credentials.items():
            vanity = creds.get('vanity_name')
            if vanity:
                result[host] = f"{vanity} ({host})"
            else:
                result[host] = host

        return result
