"""
Docker environment analysis for remote hosts.
"""

import json
from typing import List, Dict, Optional
from .connection import SSHConnection


class DockerAnalyzer:
    """Analyzes Docker environment on remote host."""

    def __init__(self, connection: SSHConnection, use_sudo: bool = False):
        """
        Initialize Docker analyzer.

        Args:
            connection: Active SSH connection to remote host
            use_sudo: Whether to use sudo for docker commands
        """
        self.connection = connection
        self.use_sudo = use_sudo

    def _run_docker_command(self, command: str) -> str:
        """
        Run docker command and return stdout.

        Args:
            command: Docker command to execute

        Returns:
            Command output

        Raises:
            RuntimeError: If command fails
        """
        if self.use_sudo:
            command = f"sudo {command}"

        stdout, stderr, exit_code = self.connection.execute_command(command)

        if exit_code != 0:
            raise RuntimeError(f"Docker command failed: {stderr}")

        return stdout.strip()

    def check_docker_available(self) -> bool:
        """
        Check if Docker is available on remote host.

        Returns:
            True if Docker is available, False otherwise
        """
        try:
            self._run_docker_command("docker --version")
            return True
        except Exception:
            return False

    def list_containers(self, all_containers: bool = True) -> List[Dict]:
        """
        List all containers on remote host.

        Args:
            all_containers: If True, include stopped containers

        Returns:
            List of container information dictionaries
        """
        flag = "-a" if all_containers else ""
        # Don't include labels in format string as they can break JSON parsing
        format_str = '{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}","status":"{{.Status}}","state":"{{.State}}"}'

        try:
            output = self._run_docker_command(f'docker ps {flag} --format \'{format_str}\'')

            if not output:
                return []

            containers = []
            for line in output.split('\n'):
                if line.strip():
                    container = json.loads(line)
                    containers.append(container)

            return containers

        except Exception as e:
            raise RuntimeError(f"Failed to list containers: {str(e)}")

    def inspect_container(self, container_id: str) -> Dict:
        """
        Get detailed container information.

        Args:
            container_id: Container ID or name

        Returns:
            Container inspection data
        """
        try:
            output = self._run_docker_command(f'docker inspect {container_id}')
            data = json.loads(output)
            return data[0] if data else {}
        except Exception as e:
            raise RuntimeError(f"Failed to inspect container {container_id}: {str(e)}")

    def get_container_volumes(self, container_id: str) -> List[Dict]:
        """
        Get volume information for a container.

        Args:
            container_id: Container ID or name

        Returns:
            List of volume mount information
        """
        try:
            inspect_data = self.inspect_container(container_id)
            mounts = inspect_data.get('Mounts', [])

            volumes = []
            for mount in mounts:
                volumes.append({
                    'type': mount.get('Type'),
                    'name': mount.get('Name'),
                    'source': mount.get('Source'),
                    'destination': mount.get('Destination'),
                    'mode': mount.get('Mode'),
                    'rw': mount.get('RW'),
                })

            return volumes

        except Exception as e:
            raise RuntimeError(f"Failed to get volumes for {container_id}: {str(e)}")

    def list_stacks(self) -> Dict[str, List[Dict]]:
        """
        Group containers by Docker Compose project/stack.

        Returns:
            Dictionary mapping project names to container lists
        """
        try:
            containers = self.list_containers()
            stacks = {}

            for container in containers:
                # Get labels from inspect to check for compose project
                try:
                    inspect_data = self.inspect_container(container['id'])
                    labels = inspect_data.get('Config', {}).get('Labels', {})

                    # Check for docker-compose project label
                    project = (labels.get('com.docker.compose.project') or
                              labels.get('com.docker.compose.project.name'))

                    if project:
                        if project not in stacks:
                            stacks[project] = []
                        stacks[project].append(container)
                except Exception:
                    # Skip containers that can't be inspected
                    continue

            return stacks

        except Exception as e:
            raise RuntimeError(f"Failed to list stacks: {str(e)}")

    def get_networks(self) -> List[Dict]:
        """
        List all Docker networks.

        Returns:
            List of network information
        """
        try:
            output = self._run_docker_command('docker network ls --format "{{.ID}}"')

            if not output:
                return []

            networks = []
            for network_id in output.split('\n'):
                if network_id.strip():
                    inspect_output = self._run_docker_command(f'docker network inspect {network_id}')
                    network_data = json.loads(inspect_output)
                    if network_data:
                        networks.append(network_data[0])

            return networks

        except Exception as e:
            raise RuntimeError(f"Failed to list networks: {str(e)}")

    def get_container_networks(self, container_id: str) -> List[str]:
        """
        Get networks that a container is connected to.

        Args:
            container_id: Container ID or name

        Returns:
            List of network names
        """
        try:
            inspect_data = self.inspect_container(container_id)
            networks = inspect_data.get('NetworkSettings', {}).get('Networks', {})
            return list(networks.keys())
        except Exception as e:
            raise RuntimeError(f"Failed to get networks for {container_id}: {str(e)}")

    def find_compose_file(self, container_id: str) -> Optional[str]:
        """
        Try to locate docker-compose.yml file for a container.

        Args:
            container_id: Container ID or name

        Returns:
            Path to compose file if found, None otherwise
        """
        try:
            inspect_data = self.inspect_container(container_id)
            labels = inspect_data.get('Config', {}).get('Labels', {})

            # Check for compose working directory label
            working_dir = (labels.get('com.docker.compose.project.working_dir') or
                          labels.get('com.docker.compose.project.config_files'))

            if working_dir:
                # Common compose file names
                compose_files = [
                    f"{working_dir}/docker-compose.yml",
                    f"{working_dir}/docker-compose.yaml",
                    f"{working_dir}/compose.yml",
                    f"{working_dir}/compose.yaml",
                ]

                for compose_file in compose_files:
                    if self.connection.file_exists(compose_file):
                        return compose_file

            return None

        except Exception:
            return None

    def get_docker_version(self) -> Dict:
        """
        Get Docker version information.

        Returns:
            Dictionary with Docker version details
        """
        try:
            output = self._run_docker_command('docker version --format "{{json .}}"')
            return json.loads(output)
        except Exception as e:
            raise RuntimeError(f"Failed to get Docker version: {str(e)}")

    def get_container_logs(self, container_id: str, lines: int = 100) -> str:
        """
        Get recent logs from a container.

        Args:
            container_id: Container ID or name
            lines: Number of log lines to retrieve

        Returns:
            Container logs
        """
        try:
            stdout, _, _ = self.connection.execute_command(
                f'docker logs --tail {lines} {container_id}'
            )
            return stdout
        except Exception as e:
            raise RuntimeError(f"Failed to get logs for {container_id}: {str(e)}")

    def export_container_config(self, container_id: str) -> Dict:
        """
        Export comprehensive container configuration for backup.

        Args:
            container_id: Container ID or name

        Returns:
            Dictionary with all necessary config for restore
        """
        try:
            inspect_data = self.inspect_container(container_id)
            config = inspect_data.get('Config', {})
            host_config = inspect_data.get('HostConfig', {})
            network_settings = inspect_data.get('NetworkSettings', {})

            return {
                'name': inspect_data.get('Name', '').lstrip('/'),
                'image': config.get('Image'),
                'cmd': config.get('Cmd'),
                'entrypoint': config.get('Entrypoint'),
                'env': config.get('Env', []),
                'labels': config.get('Labels', {}),
                'working_dir': config.get('WorkingDir'),
                'user': config.get('User'),
                'hostname': config.get('Hostname'),
                'domainname': config.get('Domainname'),
                'exposed_ports': config.get('ExposedPorts', {}),
                'volumes': config.get('Volumes', {}),
                'network_mode': host_config.get('NetworkMode'),
                'port_bindings': host_config.get('PortBindings', {}),
                'restart_policy': host_config.get('RestartPolicy', {}),
                'privileged': host_config.get('Privileged', False),
                'cap_add': host_config.get('CapAdd'),
                'cap_drop': host_config.get('CapDrop'),
                'devices': host_config.get('Devices', []),
                'dns': host_config.get('Dns', []),
                'extra_hosts': host_config.get('ExtraHosts', []),
                'networks': network_settings.get('Networks', {}),
                'mounts': inspect_data.get('Mounts', []),
            }

        except Exception as e:
            raise RuntimeError(f"Failed to export config for {container_id}: {str(e)}")
