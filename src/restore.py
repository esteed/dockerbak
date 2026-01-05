"""
Generate restore instructions for backed-up Docker containers.
"""

import json
from pathlib import Path
from typing import Dict, List
from .local_sudo import LocalSudoHelper


class RestoreInstructionsGenerator:
    """Generates comprehensive restore instructions."""

    def __init__(self, backup_dir: Path, local_sudo: bool = False):
        """
        Initialize restore instructions generator.

        Args:
            backup_dir: Path to backup directory
            local_sudo: Whether to use sudo for reading backup files
        """
        self.backup_dir = backup_dir
        self.local_sudo_helper = LocalSudoHelper(use_sudo=local_sudo)

    def generate_instructions(self) -> Path:
        """
        Generate complete restore instructions.

        Returns:
            Path to generated instructions file
        """
        instructions = []

        instructions.append("# Docker Container Restore Instructions\n")
        instructions.append(f"Backup Directory: `{self.backup_dir}`\n")
        instructions.append(f"Generated: {self._get_timestamp()}\n")

        # Prerequisites
        instructions.append("\n## Prerequisites\n")
        instructions.append("Before restoring, ensure you have:\n")
        instructions.append("- Docker installed and running on the target system\n")
        instructions.append("- Sufficient disk space for volumes and images\n")
        instructions.append("- Network connectivity to pull required Docker images\n")
        instructions.append("- Root or sudo privileges\n")

        # Find all container backups using sudo if needed
        container_dirs = self._list_subdirectories(self.backup_dir)

        if not container_dirs:
            instructions.append("\nNo container backups found.\n")
        else:
            # Check if this is a stack backup
            has_compose = any(self._file_exists(d / "docker-compose.yml") for d in container_dirs)

            if has_compose:
                instructions.extend(self._generate_stack_instructions())
            else:
                instructions.extend(self._generate_individual_instructions(container_dirs))

        # Verification steps
        instructions.append("\n## Verification\n")
        instructions.append("After restoration, verify containers are running:\n")
        instructions.append("```bash\n")
        instructions.append("docker ps\n")
        instructions.append("```\n")

        instructions.append("\nCheck container logs for errors:\n")
        instructions.append("```bash\n")
        instructions.append("docker logs <container_name>\n")
        instructions.append("```\n")

        # Troubleshooting
        instructions.append("\n## Troubleshooting\n")
        instructions.append("### Container won't start\n")
        instructions.append("- Check logs: `docker logs <container_name>`\n")
        instructions.append("- Verify image is available: `docker images`\n")
        instructions.append("- Check port conflicts: `docker ps` and `netstat -tulpn`\n")
        instructions.append("- Ensure volumes are properly restored\n")

        instructions.append("\n### Network issues\n")
        instructions.append("- Verify networks exist: `docker network ls`\n")
        instructions.append("- Recreate networks if needed (see steps above)\n")
        instructions.append("- Check network configuration in container\n")

        instructions.append("\n### Volume data issues\n")
        instructions.append("- Verify volume exists: `docker volume ls`\n")
        instructions.append("- Check volume permissions\n")
        instructions.append("- Ensure tar extraction completed successfully\n")

        # Save instructions
        instructions_file = self.backup_dir / "RESTORE_INSTRUCTIONS.md"
        content = '\n'.join(instructions)
        self.local_sudo_helper.write_file(instructions_file, content)

        return instructions_file

    def _generate_stack_instructions(self) -> List[str]:
        """Generate instructions for Docker Compose stack restoration."""
        instructions = []

        instructions.append("\n## Stack Restoration (Docker Compose)\n")
        instructions.append("This backup contains a Docker Compose stack.\n")

        # Find compose file
        compose_file = None
        for d in self._list_subdirectories(self.backup_dir):
            cf = d / "docker-compose.yml"
            if self._file_exists(cf):
                compose_file = cf
                break

        if compose_file:
            instructions.append("\n### Step 1: Restore Volumes\n")
            instructions.append("Before starting the stack, restore volume data:\n\n")

            # Get all containers in backup
            for container_dir in self._list_subdirectories(self.backup_dir):
                volumes_dir = container_dir / "volumes"
                if self._dir_exists(volumes_dir):
                    instructions.append(f"#### {container_dir.name} volumes:\n")
                    instructions.extend(self._generate_volume_restore_steps(volumes_dir))

            instructions.append("\n### Step 2: Create Networks (if needed)\n")
            instructions.append("Networks will be created automatically by docker-compose.\n")
            instructions.append("If you need custom network configurations, create them manually first.\n")

            instructions.append("\n### Step 3: Deploy Stack\n")
            instructions.append("```bash\n")
            instructions.append(f"cd {compose_file.parent}\n")
            instructions.append("docker-compose up -d\n")
            instructions.append("```\n")

        return instructions

    def _generate_individual_instructions(self, container_dirs: List[Path]) -> List[str]:
        """Generate instructions for individual container restoration."""
        instructions = []

        instructions.append("\n## Individual Container Restoration\n")

        for container_dir in sorted(container_dirs):
            instructions.append(f"\n### Restoring: {container_dir.name}\n")

            metadata_file = container_dir / "metadata.json"
            if not self._file_exists(metadata_file):
                instructions.append(f"⚠️  No metadata found for {container_dir.name}\n")
                continue

            metadata = self.local_sudo_helper.read_json(metadata_file)

            # Step 1: Networks
            networks_file = container_dir / "networks.json"
            if self._file_exists(networks_file):
                networks = self.local_sudo_helper.read_json(networks_file)
                if networks:
                    instructions.append("\n#### Step 1: Create Networks\n")
                    instructions.extend(self._generate_network_create_commands(networks))

            # Step 2: Volumes
            volumes_dir = container_dir / "volumes"
            if self._dir_exists(volumes_dir):
                instructions.append("\n#### Step 2: Restore Volumes\n")
                instructions.extend(self._generate_volume_restore_steps(volumes_dir))

            # Step 3: Pull image
            instructions.append("\n#### Step 3: Pull Image\n")
            instructions.append("```bash\n")
            instructions.append(f"docker pull {metadata['image']}\n")
            instructions.append("```\n")

            # Step 4: Run container
            instructions.append("\n#### Step 4: Create Container\n")
            docker_run_cmd = self._generate_docker_run_command(metadata)
            instructions.append("```bash\n")
            instructions.append(docker_run_cmd)
            instructions.append("\n```\n")

        return instructions

    def _generate_network_create_commands(self, networks: Dict) -> List[str]:
        """Generate docker network create commands."""
        commands = []
        commands.append("```bash\n")

        for network_name, network_config in networks.items():
            if network_name in ['bridge', 'host', 'none']:
                continue  # Skip default networks

            cmd = f"docker network create {network_name}"
            commands.append(f"{cmd}\n")

        commands.append("```\n")
        return commands

    def _generate_volume_restore_steps(self, volumes_dir: Path) -> List[str]:
        """Generate volume restoration steps."""
        steps = []

        volume_archives = self._glob_files(volumes_dir, "*.tar.gz")
        volume_infos = self._glob_files(volumes_dir, "*.json")

        if not volume_archives:
            steps.append("No volumes to restore.\n")
            return steps

        steps.append("```bash\n")

        for info_file in volume_infos:
            volume_info = self.local_sudo_helper.read_json(info_file)

            destination = volume_info.get('destination', '')
            backup_file = volume_info.get('backup_file', '')
            archive_path = volumes_dir / backup_file

            if not self._file_exists(archive_path):
                continue

            # Create volume name from destination
            volume_name = destination.replace('/', '_').strip('_') + "_restored"

            steps.append(f"# Restore {destination}\n")
            steps.append(f"docker volume create {volume_name}\n")
            steps.append(
                f"docker run --rm "
                f"-v {volume_name}:/restore "
                f"-v {archive_path.absolute().parent}:/backup "
                f"alpine "
                f"tar xzf /backup/{backup_file} -C /restore\n"
            )
            steps.append("\n")

        steps.append("```\n")
        steps.append("\n⚠️  **Note**: Volume names have '_restored' suffix. ")
        steps.append("Update the docker run command below to use these volume names.\n")

        return steps

    def _generate_docker_run_command(self, metadata: Dict) -> str:
        """Generate docker run command from metadata."""
        parts = ["docker run -d"]

        # Name
        if metadata.get('name'):
            parts.append(f"--name {metadata['name']}")

        # Hostname
        if metadata.get('hostname'):
            parts.append(f"--hostname {metadata['hostname']}")

        # Environment variables
        for env in metadata.get('env', []):
            # Escape quotes in env values
            env_escaped = env.replace('"', '\\"')
            parts.append(f'-e "{env_escaped}"')

        # Labels
        for key, value in metadata.get('labels', {}).items():
            value_escaped = value.replace('"', '\\"')
            parts.append(f'--label "{key}={value_escaped}"')

        # Port bindings
        for container_port, host_bindings in metadata.get('port_bindings', {}).items():
            if host_bindings:
                for binding in host_bindings:
                    host_port = binding.get('HostPort', '')
                    host_ip = binding.get('HostIp', '')
                    if host_ip:
                        parts.append(f"-p {host_ip}:{host_port}:{container_port}")
                    elif host_port:
                        parts.append(f"-p {host_port}:{container_port}")

        # Restart policy
        restart_policy = metadata.get('restart_policy', {})
        if restart_policy.get('Name'):
            policy_name = restart_policy['Name']
            if policy_name == 'on-failure':
                max_retry = restart_policy.get('MaximumRetryCount', 0)
                parts.append(f"--restart on-failure:{max_retry}")
            else:
                parts.append(f"--restart {policy_name}")

        # Network
        if metadata.get('network_mode'):
            parts.append(f"--network {metadata['network_mode']}")

        # Volumes (use _restored suffix as noted in volume restore steps)
        for mount in metadata.get('mounts', []):
            destination = mount.get('Destination', '')
            volume_name = destination.replace('/', '_').strip('_') + "_restored"
            parts.append(f"-v {volume_name}:{destination}")

        # Privileged
        if metadata.get('privileged'):
            parts.append("--privileged")

        # Working directory
        if metadata.get('working_dir'):
            parts.append(f"--workdir {metadata['working_dir']}")

        # User
        if metadata.get('user'):
            parts.append(f"--user {metadata['user']}")

        # Image (must be last before command)
        parts.append(metadata['image'])

        # Command
        if metadata.get('cmd'):
            cmd_str = ' '.join(metadata['cmd'])
            parts.append(cmd_str)

        # Join with backslashes for readability
        return ' \\\n  '.join(parts)

    def _get_timestamp(self) -> str:
        """Get formatted timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _list_subdirectories(self, path: Path) -> List[Path]:
        """
        List subdirectories with sudo support.

        Args:
            path: Path to list

        Returns:
            List of subdirectory paths
        """
        if self.local_sudo_helper.use_sudo:
            import subprocess
            # Use sudo find to list immediate subdirectories
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
            # Use regular path operations
            return [d for d in path.iterdir() if d.is_dir()]

    def _file_exists(self, path: Path) -> bool:
        """
        Check if file exists with sudo support.

        Args:
            path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        if self.local_sudo_helper.use_sudo:
            import subprocess
            # Use sudo test to check file existence
            result = subprocess.run(
                ['sudo', 'test', '-f', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.exists()

    def _dir_exists(self, path: Path) -> bool:
        """
        Check if directory exists with sudo support.

        Args:
            path: Path to check

        Returns:
            True if directory exists, False otherwise
        """
        if self.local_sudo_helper.use_sudo:
            import subprocess
            # Use sudo test to check directory existence
            result = subprocess.run(
                ['sudo', 'test', '-d', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.is_dir()

    def _glob_files(self, path: Path, pattern: str) -> List[Path]:
        """
        Glob files with sudo support.

        Args:
            path: Directory to search in
            pattern: Glob pattern (e.g., "*.tar.gz")

        Returns:
            List of matching file paths
        """
        if self.local_sudo_helper.use_sudo:
            import subprocess
            # Use sudo find with -name pattern
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
