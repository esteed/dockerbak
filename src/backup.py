"""
Docker container and volume backup operations.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .connection import SSHConnection
from .docker_analyzer import DockerAnalyzer
from .local_sudo import LocalSudoHelper

logger = logging.getLogger('dockerbak.backup')


class DockerBackup:
    """Handles Docker container and volume backups."""

    def __init__(self, connection: SSHConnection, analyzer: DockerAnalyzer, local_sudo: bool = False):
        """
        Initialize backup handler.

        Args:
            connection: Active SSH connection
            analyzer: Docker analyzer instance
            local_sudo: Whether to use sudo for local file operations
        """
        self.connection = connection
        self.analyzer = analyzer
        self.use_sudo = analyzer.use_sudo
        self.local_sudo_helper = LocalSudoHelper(use_sudo=local_sudo)

    def backup_container(self, container_id: str, output_dir: Path,
                        include_volumes: bool = True,
                        include_compose: bool = True) -> Dict:
        """
        Create full backup of a container.

        Args:
            container_id: Container ID or name
            output_dir: Directory to store backup
            include_volumes: Whether to backup volume data
            include_compose: Whether to include docker-compose file

        Returns:
            Dictionary with backup metadata
        """
        logger.debug(f"backup_container: container_id={container_id}, output_dir={output_dir}")
        logger.debug(f"backup_container: include_volumes={include_volumes}, include_compose={include_compose}")

        # Get container name for directory
        inspect_data = self.analyzer.inspect_container(container_id)
        container_name = inspect_data.get('Name', '').lstrip('/')
        logger.debug(f"backup_container: container_name={container_name}")

        # Create container backup directory
        container_dir = output_dir / container_name
        logger.debug(f"backup_container: creating container_dir={container_dir}")
        self.local_sudo_helper.mkdir(container_dir)
        logger.debug(f"backup_container: container_dir created successfully")

        backup_info = {
            'container_id': container_id,
            'container_name': container_name,
            'timestamp': datetime.now().isoformat(),
            'files': []
        }

        # 1. Backup metadata
        metadata_file = self.backup_metadata(container_id, container_dir)
        backup_info['files'].append(str(metadata_file.relative_to(output_dir)))

        # 2. Backup volumes
        if include_volumes:
            volume_files = self.backup_volumes(container_id, container_dir)
            backup_info['files'].extend([str(f.relative_to(output_dir)) for f in volume_files])
            backup_info['volume_count'] = len(volume_files)

        # 3. Backup networks
        networks_file = self.backup_networks(container_id, container_dir)
        backup_info['files'].append(str(networks_file.relative_to(output_dir)))

        # 4. Try to backup docker-compose file
        if include_compose:
            compose_file = self.backup_compose_file(container_id, container_dir)
            if compose_file:
                backup_info['files'].append(str(compose_file.relative_to(output_dir)))
                backup_info['has_compose'] = True
            else:
                backup_info['has_compose'] = False

        return backup_info

    def backup_metadata(self, container_id: str, output_dir: Path) -> Path:
        """
        Backup container metadata and configuration.

        Args:
            container_id: Container ID or name
            output_dir: Directory to store backup

        Returns:
            Path to metadata file
        """
        logger.debug(f"backup_metadata: container_id={container_id}, output_dir={output_dir}")

        config = self.analyzer.export_container_config(container_id)
        logger.debug(f"backup_metadata: got config with {len(config)} keys")

        metadata_file = output_dir / "metadata.json"
        logger.debug(f"backup_metadata: writing to {metadata_file}")
        self.local_sudo_helper.write_json(metadata_file, config)
        logger.debug(f"backup_metadata: metadata written successfully")

        return metadata_file

    def backup_volumes(self, container_id: str, output_dir: Path) -> List[Path]:
        """
        Backup all volumes attached to a container.

        Args:
            container_id: Container ID or name
            output_dir: Directory to store backup

        Returns:
            List of paths to volume backup files
        """
        volumes = self.analyzer.get_container_volumes(container_id)

        if not volumes:
            return []

        volumes_dir = output_dir / "volumes"
        self.local_sudo_helper.mkdir(volumes_dir)

        backup_files = []

        for volume in volumes:
            volume_type = volume.get('type')
            source = volume.get('source')
            destination = volume.get('destination')

            if not source:
                continue

            # Create safe filename from destination path
            safe_name = destination.replace('/', '_').strip('_')
            backup_file = volumes_dir / f"{safe_name}.tar.gz"

            try:
                # Create tar archive of volume on remote host
                temp_tar = f"/tmp/dockerbak_{safe_name}.tar.gz"

                # Use docker run to access volume and create archive
                tar_command = (
                    f'docker run --rm '
                    f'-v {source}:/backup_source:ro '
                    f'-v /tmp:/backup_dest '
                    f'alpine '
                    f'tar czf /backup_dest/dockerbak_{safe_name}.tar.gz -C /backup_source .'
                )

                if self.use_sudo:
                    tar_command = f"sudo {tar_command}"

                stdout, stderr, exit_code = self.connection.execute_command(
                    tar_command,
                    timeout=300  # 5 minutes for large volumes
                )

                if exit_code == 0:
                    # Download the archive to temp location first (SFTP can't write to sudo dirs)
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
                        local_temp = tmp.name

                    self.connection.download_file(temp_tar, local_temp)

                    # Get file size BEFORE moving (can't stat root-owned files)
                    from pathlib import Path as PathLib
                    file_size = PathLib(local_temp).stat().st_size

                    # Move to final location with sudo if needed
                    if self.local_sudo_helper.use_sudo:
                        import subprocess
                        subprocess.run(['sudo', 'mv', local_temp, str(backup_file)], check=True)
                    else:
                        import shutil
                        shutil.move(local_temp, str(backup_file))

                    # Clean up remote temp file
                    self.connection.execute_command(f'rm -f {temp_tar}')

                    # Store volume metadata
                    volume_info = {
                        'type': volume_type,
                        'source': source,
                        'destination': destination,
                        'mode': volume.get('mode'),
                        'rw': volume.get('rw'),
                        'backup_file': backup_file.name,
                        'size': file_size
                    }

                    # Save volume info
                    info_file = volumes_dir / f"{safe_name}.json"
                    self.local_sudo_helper.write_json(info_file, volume_info)

                    backup_files.append(backup_file)

            except Exception as e:
                print(f"Warning: Failed to backup volume {destination}: {str(e)}")

        return backup_files

    def backup_networks(self, container_id: str, output_dir: Path) -> Path:
        """
        Backup network configuration for a container.

        Args:
            container_id: Container ID or name
            output_dir: Directory to store backup

        Returns:
            Path to networks file
        """
        inspect_data = self.analyzer.inspect_container(container_id)
        networks = inspect_data.get('NetworkSettings', {}).get('Networks', {})

        networks_file = output_dir / "networks.json"
        self.local_sudo_helper.write_json(networks_file, networks)

        return networks_file

    def backup_compose_file(self, container_id: str, output_dir: Path) -> Optional[Path]:
        """
        Backup docker-compose file if found.

        Args:
            container_id: Container ID or name
            output_dir: Directory to store backup

        Returns:
            Path to compose file if found, None otherwise
        """
        compose_path = self.analyzer.find_compose_file(container_id)

        if not compose_path:
            return None

        try:
            # Download compose file to temp location first (SFTP can't write to sudo dirs)
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.yml') as tmp:
                local_temp = tmp.name

            self.connection.download_file(compose_path, local_temp)

            # Move to final location with sudo if needed
            local_compose = output_dir / "docker-compose.yml"
            if self.local_sudo_helper.use_sudo:
                import subprocess
                subprocess.run(['sudo', 'mv', local_temp, str(local_compose)], check=True)
            else:
                import shutil
                shutil.move(local_temp, str(local_compose))

            return local_compose
        except Exception:
            return None

    def backup_stack(self, project_name: str, containers: List[Dict],
                    output_dir: Path) -> Dict:
        """
        Backup entire Docker Compose stack.

        Args:
            project_name: Stack/project name
            containers: List of containers in stack
            output_dir: Directory to store backup

        Returns:
            Dictionary with stack backup metadata
        """
        stack_dir = output_dir / project_name
        self.local_sudo_helper.mkdir(stack_dir)

        stack_info = {
            'project_name': project_name,
            'timestamp': datetime.now().isoformat(),
            'containers': [],
            'compose_file': None
        }

        # Backup each container in the stack
        for container in containers:
            container_id = container['id']
            container_backup = self.backup_container(
                container_id,
                stack_dir,
                include_volumes=True,
                include_compose=False  # We'll get it once for the stack
            )
            stack_info['containers'].append(container_backup)

        # Try to get compose file from first container
        if containers:
            compose_file = self.backup_compose_file(containers[0]['id'], stack_dir)
            if compose_file:
                stack_info['compose_file'] = str(compose_file.relative_to(output_dir))

        return stack_info

    def generate_manifest(self, backup_dir: Path, backup_info: Dict) -> Path:
        """
        Generate backup manifest with checksums.

        Args:
            backup_dir: Backup directory
            backup_info: Backup information dictionary

        Returns:
            Path to manifest file
        """
        manifest = {
            'backup_info': backup_info,
            'files': {}
        }

        # Calculate checksums for all files
        # Use sudo find if needed, otherwise use rglob
        if self.local_sudo_helper.use_sudo:
            import subprocess
            result = subprocess.run(
                ['sudo', 'find', str(backup_dir), '-type', 'f', '-name', '*.json', '-o', '-type', 'f', '-name', '*.tar.gz', '-o', '-type', 'f', '-name', '*.yml'],
                capture_output=True, text=True
            )
            file_paths = [Path(f) for f in result.stdout.strip().split('\n') if f and 'manifest.json' not in f]
        else:
            file_paths = [f for f in backup_dir.rglob('*') if f.is_file() and f.name != 'manifest.json']

        for file_path in file_paths:
            # Skip manifest itself
            if file_path.name == 'manifest.json':
                continue

            checksum = self._calculate_checksum(file_path)
            relative_path = str(file_path.relative_to(backup_dir))

            # Get file size with sudo if needed
            if self.local_sudo_helper.use_sudo:
                import subprocess
                stat_result = subprocess.run(
                    ['sudo', 'stat', '-c', '%s', str(file_path)],
                    capture_output=True, text=True
                )
                file_size = int(stat_result.stdout.strip()) if stat_result.returncode == 0 else 0
            else:
                file_size = file_path.stat().st_size

            manifest['files'][relative_path] = {
                'checksum': checksum,
                'size': file_size
            }

        # Save manifest
        manifest_file = backup_dir / "manifest.json"
        self.local_sudo_helper.write_json(manifest_file, manifest)

        return manifest_file

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of checksum
        """
        sha256 = hashlib.sha256()

        # Read file with sudo if needed
        if self.local_sudo_helper.use_sudo:
            # For large files, we need to read in chunks even with sudo
            import subprocess
            proc = subprocess.Popen(
                ['sudo', 'cat', str(file_path)],
                stdout=subprocess.PIPE
            )
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
            proc.wait()
        else:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)

        return sha256.hexdigest()

    def create_backup_directory(self, base_dir: Optional[str] = None,
                               container_name: Optional[str] = None) -> Path:
        """
        Create timestamped backup directory with optional container name.

        Args:
            base_dir: Base directory for backups (default: current directory)
            container_name: Container name to include in directory name

        Returns:
            Path to backup directory
        """
        logger.debug(f"create_backup_directory: base_dir={base_dir}, container_name={container_name}")

        if base_dir:
            base_path = Path(base_dir)
        else:
            base_path = Path.cwd()

        logger.debug(f"create_backup_directory: base_path={base_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Include container name if provided
        if container_name:
            # Sanitize container name for filesystem
            safe_name = container_name.replace('/', '_').replace(' ', '_').strip('_')
            backup_dir = base_path / f"{safe_name}_{timestamp}"
        else:
            backup_dir = base_path / f"backup_{timestamp}"

        logger.debug(f"create_backup_directory: backup_dir={backup_dir}, calling mkdir")

        # Use sudo helper to create directory
        self.local_sudo_helper.mkdir(backup_dir)

        logger.debug(f"create_backup_directory: mkdir completed successfully, returning {backup_dir}")
        return backup_dir
