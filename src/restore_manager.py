"""
Restore manager for executing container restoration from backups.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from .connection import SSHConnection
from .docker_analyzer import DockerAnalyzer
from .local_sudo import LocalSudoHelper


class RestoreManager:
    """Manages restoration of containers from backups."""

    def __init__(self, connection: SSHConnection, analyzer: DockerAnalyzer, local_sudo: bool = False):
        """
        Initialize restore manager.

        Args:
            connection: Active SSH connection to target host
            analyzer: Docker analyzer for target host
            local_sudo: Whether to use sudo for local file operations
        """
        self.connection = connection
        self.analyzer = analyzer
        self.local_sudo_helper = LocalSudoHelper(use_sudo=local_sudo)

    def read_backup_manifest(self, backup_dir: Path) -> Optional[Dict]:
        """
        Read backup manifest.

        Args:
            backup_dir: Path to backup directory

        Returns:
            Manifest dictionary or None if not found
        """
        manifest_file = backup_dir / "manifest.json"
        if not self._file_exists(manifest_file):
            return None

        return self.local_sudo_helper.read_json(manifest_file)

    def list_containers_in_backup(self, backup_dir: Path) -> List[Dict]:
        """
        List all containers in a backup.

        Args:
            backup_dir: Path to backup directory

        Returns:
            List of container information
        """
        containers = []

        for item in self._list_subdirectories(backup_dir):
            if item.name != '__pycache__':
                metadata_file = item / "metadata.json"
                if self._file_exists(metadata_file):
                    metadata = self.local_sudo_helper.read_json(metadata_file)
                    containers.append({
                        'name': metadata.get('name'),
                        'image': metadata.get('image'),
                        'backup_dir': item
                    })

        return containers

    def restore_networks(self, backup_dir: Path) -> bool:
        """
        Restore Docker networks from backup.

        Args:
            backup_dir: Container backup directory

        Returns:
            True if successful
        """
        networks_file = backup_dir / "networks.json"
        if not self._file_exists(networks_file):
            return True  # No networks to restore

        networks = self.local_sudo_helper.read_json(networks_file)

        for network_name, network_config in networks.items():
            # Skip default networks
            if network_name in ['bridge', 'host', 'none']:
                continue

            # Check if network already exists
            try:
                existing_networks = self.analyzer.get_networks()
                if any(n.get('Name') == network_name for n in existing_networks):
                    continue  # Network already exists

                # Create network
                cmd = f'docker network create {network_name}'
                if self.analyzer.use_sudo:
                    cmd = f'sudo {cmd}'

                stdout, stderr, exit_code = self.connection.execute_command(cmd)
                if exit_code != 0 and 'already exists' not in stderr:
                    raise RuntimeError(f"Failed to create network {network_name}: {stderr}")

            except Exception as e:
                print(f"Warning: Could not create network {network_name}: {str(e)}")

        return True

    def restore_volumes(self, backup_dir: Path) -> Dict[str, str]:
        """
        Restore Docker volumes from backup.

        Args:
            backup_dir: Container backup directory

        Returns:
            Dictionary mapping original destinations to new volume names
        """
        volumes_dir = backup_dir / "volumes"
        if not self._dir_exists(volumes_dir):
            return {}

        volume_mapping = {}

        # Read volume info files
        for info_file in self._glob_files(volumes_dir, "*.json"):
            volume_info = self.local_sudo_helper.read_json(info_file)

            destination = volume_info.get('destination')
            backup_file = volume_info.get('backup_file')
            archive_path = volumes_dir / backup_file

            if not self._file_exists(archive_path):
                continue

            # Create volume name
            volume_name = destination.replace('/', '_').strip('_') + "_restored"

            try:
                # Create volume
                cmd = f'docker volume create {volume_name}'
                if self.analyzer.use_sudo:
                    cmd = f'sudo {cmd}'

                stdout, stderr, exit_code = self.connection.execute_command(cmd)
                if exit_code != 0 and 'already exists' not in stderr:
                    raise RuntimeError(f"Failed to create volume: {stderr}")

                # Upload archive to remote host
                # If using local sudo, copy to temp location first (SFTP can't read root-owned files)
                remote_archive = f'/tmp/{backup_file}'

                if self.local_sudo_helper.use_sudo:
                    import tempfile
                    import subprocess

                    # Create temp file for upload
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
                        temp_upload_path = tmp.name

                    # Copy root-owned file to temp location with sudo
                    subprocess.run(['sudo', 'cp', str(archive_path), temp_upload_path], check=True)
                    # Make it readable by current user
                    subprocess.run(['sudo', 'chown', str(os.getuid()), temp_upload_path], check=True)

                    try:
                        # Upload the temp file
                        self.connection.sftp.put(temp_upload_path, remote_archive)
                    finally:
                        # Clean up temp file
                        import os as os_module
                        os_module.unlink(temp_upload_path)
                else:
                    # Normal upload without sudo
                    self.connection.sftp.put(str(archive_path), remote_archive)

                # Extract archive into volume
                extract_cmd = (
                    f'docker run --rm '
                    f'-v {volume_name}:/restore '
                    f'-v /tmp:/backup '
                    f'alpine '
                    f'tar xzf /backup/{backup_file} -C /restore'
                )

                if self.analyzer.use_sudo:
                    extract_cmd = f'sudo {extract_cmd}'

                stdout, stderr, exit_code = self.connection.execute_command(
                    extract_cmd,
                    timeout=300
                )

                if exit_code != 0:
                    raise RuntimeError(f"Failed to extract volume: {stderr}")

                # Clean up remote archive
                cleanup_cmd = f'rm -f {remote_archive}'
                if self.analyzer.use_sudo:
                    cleanup_cmd = f'sudo {cleanup_cmd}'
                self.connection.execute_command(cleanup_cmd)

                volume_mapping[destination] = volume_name

            except Exception as e:
                print(f"Warning: Could not restore volume for {destination}: {str(e)}")

        return volume_mapping

    def restore_container(self, backup_dir: Path, volume_mapping: Dict[str, str]) -> bool:
        """
        Restore a container from backup.

        Args:
            backup_dir: Container backup directory
            volume_mapping: Mapping of original volume paths to restored volume names

        Returns:
            True if successful
        """
        metadata_file = backup_dir / "metadata.json"
        if not self._file_exists(metadata_file):
            raise RuntimeError("No metadata.json found in backup")

        metadata = self.local_sudo_helper.read_json(metadata_file)

        # Build docker run command
        cmd_parts = ['docker', 'run', '-d']

        # Name
        if metadata.get('name'):
            cmd_parts.extend(['--name', metadata['name']])

        # Hostname
        if metadata.get('hostname'):
            cmd_parts.extend(['--hostname', metadata['hostname']])

        # Environment variables
        for env in metadata.get('env', []):
            cmd_parts.extend(['-e', f'"{env}"'])

        # Labels
        for key, value in metadata.get('labels', {}).items():
            cmd_parts.extend(['--label', f'"{key}={value}"'])

        # Port bindings
        for container_port, host_bindings in metadata.get('port_bindings', {}).items():
            if host_bindings:
                for binding in host_bindings:
                    host_port = binding.get('HostPort', '')
                    host_ip = binding.get('HostIp', '')
                    if host_ip:
                        cmd_parts.extend(['-p', f'{host_ip}:{host_port}:{container_port}'])
                    elif host_port:
                        cmd_parts.extend(['-p', f'{host_port}:{container_port}'])

        # Restart policy
        restart_policy = metadata.get('restart_policy', {})
        if restart_policy.get('Name'):
            policy_name = restart_policy['Name']
            if policy_name == 'on-failure':
                max_retry = restart_policy.get('MaximumRetryCount', 0)
                cmd_parts.extend(['--restart', f'on-failure:{max_retry}'])
            elif policy_name != 'no':
                cmd_parts.extend(['--restart', policy_name])

        # Network
        if metadata.get('network_mode'):
            cmd_parts.extend(['--network', metadata['network_mode']])

        # Volumes - use restored volume names
        for mount in metadata.get('mounts', []):
            destination = mount.get('Destination', '')
            if destination in volume_mapping:
                volume_name = volume_mapping[destination]
                cmd_parts.extend(['-v', f'{volume_name}:{destination}'])

        # Privileged
        if metadata.get('privileged'):
            cmd_parts.append('--privileged')

        # Working directory
        if metadata.get('working_dir'):
            cmd_parts.extend(['--workdir', metadata['working_dir']])

        # User
        if metadata.get('user'):
            cmd_parts.extend(['--user', metadata['user']])

        # Image
        cmd_parts.append(metadata['image'])

        # Command
        if metadata.get('cmd'):
            cmd_parts.extend(metadata['cmd'])

        # Execute docker run
        cmd = ' '.join(cmd_parts)
        if self.analyzer.use_sudo:
            cmd = f'sudo {cmd}'

        try:
            stdout, stderr, exit_code = self.connection.execute_command(cmd)
            if exit_code != 0:
                raise RuntimeError(f"Failed to create container: {stderr}")

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to restore container: {str(e)}")

    def pull_image(self, image: str) -> bool:
        """
        Pull Docker image on target host.

        Args:
            image: Image name to pull

        Returns:
            True if successful
        """
        try:
            cmd = f'docker pull {image}'
            if self.analyzer.use_sudo:
                cmd = f'sudo {cmd}'

            stdout, stderr, exit_code = self.connection.execute_command(
                cmd,
                timeout=600  # 10 minutes for large images
            )

            return exit_code == 0

        except Exception:
            return False

    def _list_subdirectories(self, path: Path) -> List[Path]:
        """List subdirectories with sudo support."""
        if self.local_sudo_helper.use_sudo:
            import subprocess
            result = subprocess.run(
                ['sudo', 'find', str(path), '-mindepth', '1', '-maxdepth', '1', '-type', 'd'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                dirs = [Path(d) for d in result.stdout.strip().split('\n') if d]
                return dirs
            return []
        else:
            return [d for d in path.iterdir() if d.is_dir()]

    def _file_exists(self, path: Path) -> bool:
        """Check if file exists with sudo support."""
        if self.local_sudo_helper.use_sudo:
            import subprocess
            result = subprocess.run(
                ['sudo', 'test', '-f', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.exists()

    def _dir_exists(self, path: Path) -> bool:
        """Check if directory exists with sudo support."""
        if self.local_sudo_helper.use_sudo:
            import subprocess
            result = subprocess.run(
                ['sudo', 'test', '-d', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.is_dir()

    def _glob_files(self, path: Path, pattern: str) -> List[Path]:
        """Glob files with sudo support."""
        if self.local_sudo_helper.use_sudo:
            import subprocess
            result = subprocess.run(
                ['sudo', 'find', str(path), '-maxdepth', '1', '-type', 'f', '-name', pattern],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                files = [Path(f) for f in result.stdout.strip().split('\n') if f]
                return sorted(files)
            return []
        else:
            return sorted(path.glob(pattern))
