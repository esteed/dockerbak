"""
CLI interface for Dockerbak.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict
import questionary
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import print as rprint

from .credentials import CredentialManager
from .connection import SSHConnection
from .docker_analyzer import DockerAnalyzer
from .backup import DockerBackup
from .restore import RestoreInstructionsGenerator
from .local_sudo import LocalSudoHelper
from .restore_manager import RestoreManager
from .backup_scanner import BackupScanner


console = Console()


class DockerBakCLI:
    """Main CLI interface for Dockerbak."""

    def __init__(self):
        """Initialize CLI."""
        self.credential_manager = CredentialManager()
        self.connection: Optional[SSHConnection] = None
        self.analyzer: Optional[DockerAnalyzer] = None
        self.backup: Optional[DockerBackup] = None
        self.use_sudo: bool = False
        self.local_sudo: bool = False

    def run(self):
        """Main CLI execution flow."""
        try:
            console.print("\n[bold blue]🐳 Dockerbak - Docker Backup & Restore Tool[/bold blue]\n")

            # Step 1: Unlock credential store (only once)
            if not self._unlock_credentials():
                console.print("[red]Failed to unlock credential store. Exiting.[/red]")
                return 1

            # Outer loop for host changes
            while True:
                # Step 2: Get or create credentials
                credentials = self._get_credentials()
                if not credentials:
                    console.print("[red]No credentials provided. Exiting.[/red]")
                    return 1

                # Step 3: Connect to remote host
                if not self._connect(credentials):
                    console.print("[red]Failed to connect to remote host. Exiting.[/red]")
                    return 1

                # Step 3.5: Detect sudo requirement
                self._detect_sudo_requirement()

                # Step 4: Check Docker availability
                if not self._check_docker():
                    console.print("[red]Docker not available on remote host. Exiting.[/red]")
                    self.connection.disconnect()
                    return 1

                # Step 5: Main menu loop
                while True:
                    action = self._main_menu()

                    if action == "backup_container":
                        self._backup_container_flow()
                    elif action == "backup_stack":
                        self._backup_stack_flow()
                    elif action == "restore_backup":
                        self._restore_backup_flow()
                    elif action == "delete_container":
                        self._delete_container_flow()
                    elif action == "list_containers":
                        self._list_containers()
                    elif action == "list_stacks":
                        self._list_stacks()
                    elif action == "manage_hosts":
                        self._manage_hosts_flow()
                    elif action == "change_host":
                        # Disconnect from current host and restart connection flow
                        console.print("\n[yellow]Disconnecting from current host...[/yellow]")
                        self.connection.disconnect()
                        console.print("[green]✓[/green] Disconnected.\n")

                        # Break from menu loop to go back to Step 2 (outer loop continues)
                        break
                    elif action == "exit":
                        # Clean exit - disconnect and return
                        self.connection.disconnect()
                        console.print("\n[green]✓[/green] Disconnected. Goodbye!\n")
                        return 0

                # If action was "change_host", the outer loop continues to reconnect
                # If action was "exit", we already returned above

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted by user. Exiting.[/yellow]\n")
            if self.connection:
                self.connection.disconnect()
            return 130
        except Exception as e:
            console.print(f"\n[red]Error: {str(e)}[/red]\n")
            if self.connection:
                self.connection.disconnect()
            return 1

    def _unlock_credentials(self) -> bool:
        """Unlock credential store with master password."""
        console.print("[cyan]Credential Store[/cyan]")

        if self.credential_manager.has_stored_credentials():
            console.print("Stored credentials found.")
        else:
            console.print("No stored credentials found. You'll be prompted to save new credentials.")

        while True:
            master_password = questionary.password(
                "Enter master password:",
                validate=lambda x: len(x) > 0
            ).ask()

            if master_password is None:
                return False

            if self.credential_manager.unlock(master_password):
                console.print("[green]✓[/green] Credential store unlocked.\n")
                return True
            else:
                console.print("[red]✗[/red] Invalid master password. Try again.\n")

    def _get_credentials(self) -> Optional[Dict]:
        """Get SSH credentials from store or prompt user."""
        # Check for existing credentials
        hosts_with_names = self.credential_manager.list_hosts_with_names()

        if hosts_with_names:
            # Show existing hosts with vanity names
            console.print("[cyan]Saved Connections:[/cyan]")
            # Create choices with display names
            display_names = list(hosts_with_names.values())
            choices = display_names + ["Add new connection"]

            selected_display = questionary.select(
                "Select a host:",
                choices=choices
            ).ask()

            if selected_display is None:
                return None

            if selected_display == "Add new connection":
                return self._prompt_new_credentials()
            else:
                # Map display name back to actual hostname
                actual_host = None
                for host, display_name in hosts_with_names.items():
                    if display_name == selected_display:
                        actual_host = host
                        break

                if actual_host:
                    # Load credentials and include the hostname
                    creds = self.credential_manager.load_credentials(actual_host)
                    if creds:
                        creds['host'] = actual_host  # Add hostname to credentials
                    return creds
                return None
        else:
            return self._prompt_new_credentials()

    def _prompt_new_credentials(self) -> Optional[Dict]:
        """Prompt user for new SSH credentials."""
        console.print("\n[cyan]New Connection[/cyan]")

        host = questionary.text("Hostname or IP:").ask()
        if not host:
            return None

        username = questionary.text("Username:", default="root").ask()
        if not username:
            return None

        port = questionary.text("Port:", default="22").ask()
        if not port:
            return None
        port = int(port)

        auth_method = questionary.select(
            "Authentication method:",
            choices=["Password", "SSH Key"],
        ).ask()

        password = None
        ssh_key_path = None

        if auth_method == "Password":
            password = questionary.password("Password:").ask()
            if not password:
                return None
        else:
            ssh_key_path = questionary.path(
                "Path to SSH private key:",
                default=str(Path.home() / ".ssh" / "id_rsa")
            ).ask()
            if not ssh_key_path:
                return None

        # Ask if user wants to save
        save = questionary.confirm(
            "Save these credentials for future use?",
            default=True
        ).ask()

        if save:
            self.credential_manager.save_credentials(
                host, username, password, ssh_key_path, port
            )
            console.print("[green]✓[/green] Credentials saved.\n")

        return {
            "username": username,
            "password": password,
            "ssh_key_path": ssh_key_path,
            "port": port
        }

    def _connect(self, credentials: Dict) -> bool:
        """Connect to remote host."""
        console.print("\n[cyan]Connecting to Remote Host[/cyan]")

        # Get host from credentials or prompt if not available
        host = credentials.get('host')
        if not host:
            host = questionary.text("Hostname or IP:").ask()
            if not host:
                return False
        else:
            console.print(f"Using saved connection: {host}")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description=f"Connecting to {host}...", total=None)

                self.connection = SSHConnection()
                self.connection.connect(
                    host=host,
                    username=credentials['username'],
                    password=credentials.get('password'),
                    ssh_key_path=credentials.get('ssh_key_path'),
                    port=credentials['port']
                )

            console.print(f"[green]✓[/green] Connected to {host}\n")
            return True

        except Exception as e:
            console.print(f"[red]✗[/red] Connection failed: {str(e)}\n")
            return False

    def _detect_sudo_for_connection(self, connection: SSHConnection) -> bool:
        """
        Detect if sudo is needed for Docker commands on a connection.

        Args:
            connection: SSH connection to test

        Returns:
            True if sudo is required, False otherwise
        """
        console.print("Testing Docker access...")

        # Try without sudo first
        try:
            stdout, stderr, exit_code = connection.execute_command("docker ps -q", timeout=10)

            if exit_code == 0:
                # Docker works without sudo
                console.print("[green]✓[/green] Docker access confirmed (no sudo required)\n")
                return False
            elif "permission denied" in stderr.lower() or "connect to the docker daemon socket" in stderr.lower():
                # Permission error - try with sudo
                console.print("[yellow]⚠[/yellow] Docker requires elevated privileges, testing with sudo...")

                stdout, stderr, exit_code = connection.execute_command("sudo docker ps -q", timeout=10)

                if exit_code == 0:
                    console.print("[green]✓[/green] Docker access confirmed (using sudo)\n")
                    return True
                else:
                    # Sudo also failed
                    console.print(f"[red]✗[/red] Docker access failed even with sudo: {stderr}\n")
                    return False
            else:
                # Some other error
                console.print(f"[yellow]⚠[/yellow] Docker test failed: {stderr}")
                console.print("[yellow]Assuming sudo is not required\n")
                return False

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not test Docker access: {str(e)}")
            console.print("[yellow]Assuming sudo is not required\n")
            return False

    def _detect_sudo_requirement(self) -> None:
        """Automatically detect if sudo is needed for Docker commands."""
        console.print("\n[cyan]Docker Configuration[/cyan]")
        self.use_sudo = self._detect_sudo_for_connection(self.connection)

    def _check_local_sudo(self, backup_dir: str) -> None:
        """Check if sudo is needed for local backup operations and enable automatically."""
        from pathlib import Path

        sudo_helper = LocalSudoHelper(use_sudo=False)
        backup_path = Path(backup_dir)

        if sudo_helper.needs_sudo(backup_path):
            console.print(f"\n[yellow]'{backup_dir}' requires elevated privileges - automatically using sudo[/yellow]\n")
            self.local_sudo = True
            # Recreate backup object with sudo enabled
            self.backup = DockerBackup(self.connection, self.analyzer, local_sudo=True)

    def _check_docker(self) -> bool:
        """Check if Docker is available on remote host."""
        console.print("[cyan]Checking Docker availability...[/cyan]")

        self.analyzer = DockerAnalyzer(self.connection, use_sudo=self.use_sudo)
        self.backup = DockerBackup(self.connection, self.analyzer, local_sudo=self.local_sudo)

        if self.analyzer.check_docker_available():
            version_info = self.analyzer.get_docker_version()
            server_version = version_info.get('Server', {}).get('Version', 'Unknown')
            console.print(f"[green]✓[/green] Docker version: {server_version}\n")
            return True
        else:
            return False

    def _main_menu(self) -> str:
        """Display main menu and get user choice."""
        console.print("\n[cyan]Main Menu[/cyan]")
        if self.connection and self.connection.host:
            console.print(f"[dim]Connected to: {self.connection.host}[/dim]\n")

        choices = [
            "Backup individual container",
            "Backup Docker Compose stack",
            "Restore from backup",
            "Delete container",
            "List all containers",
            "List all stacks",
            "Manage saved hosts",
            "Change host",
            "Exit"
        ]

        choice = questionary.select(
            "What would you like to do?",
            choices=choices
        ).ask()

        if choice is None:
            return "exit"

        action_map = {
            "Backup individual container": "backup_container",
            "Backup Docker Compose stack": "backup_stack",
            "Restore from backup": "restore_backup",
            "Delete container": "delete_container",
            "List all containers": "list_containers",
            "List all stacks": "list_stacks",
            "Manage saved hosts": "manage_hosts",
            "Change host": "change_host",
            "Exit": "exit"
        }

        return action_map.get(choice, "exit")

    def _list_containers(self):
        """Display list of all containers."""
        try:
            containers = self.analyzer.list_containers()

            if not containers:
                console.print("\n[yellow]No containers found.[/yellow]")
                return

            table = Table(title="Docker Containers")
            table.add_column("Name", style="cyan")
            table.add_column("Image", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("State")

            for container in containers:
                table.add_row(
                    container['name'],
                    container['image'],
                    container['status'],
                    container['state']
                )

            console.print()
            console.print(table)
            console.print()

        except Exception as e:
            console.print(f"[red]Error listing containers: {str(e)}[/red]")

    def _list_stacks(self):
        """Display list of all Docker Compose stacks."""
        try:
            stacks = self.analyzer.list_stacks()

            if not stacks:
                console.print("\n[yellow]No Docker Compose stacks found.[/yellow]")
                return

            for project_name, containers in stacks.items():
                table = Table(title=f"Stack: {project_name}")
                table.add_column("Container", style="cyan")
                table.add_column("Image", style="green")
                table.add_column("Status", style="yellow")

                for container in containers:
                    table.add_row(
                        container['name'],
                        container['image'],
                        container['status']
                    )

                console.print()
                console.print(table)

            console.print()

        except Exception as e:
            console.print(f"[red]Error listing stacks: {str(e)}[/red]")

    def _backup_container_flow(self):
        """Flow for backing up individual container."""
        try:
            # Get containers
            containers = self.analyzer.list_containers()

            if not containers:
                console.print("\n[yellow]No containers found.[/yellow]")
                return

            # Let user select containers
            choices = [f"{c['name']} ({c['image']})" for c in containers]
            selected = questionary.checkbox(
                "Select containers to backup:",
                choices=choices
            ).ask()

            if not selected:
                return

            # Get backup location
            backup_dir = questionary.path(
                "Backup directory:",
                default="/backups",
                only_directories=True
            ).ask()

            if not backup_dir:
                return

            # Create backup
            self._perform_backup(containers, selected, backup_dir, is_stack=False)

        except Exception as e:
            console.print(f"[red]Error during backup: {str(e)}[/red]")

    def _backup_stack_flow(self):
        """Flow for backing up Docker Compose stack."""
        try:
            # Get stacks
            stacks = self.analyzer.list_stacks()

            if not stacks:
                console.print("\n[yellow]No Docker Compose stacks found.[/yellow]")
                return

            # Let user select stack
            choices = list(stacks.keys())
            selected_stack = questionary.select(
                "Select stack to backup:",
                choices=choices
            ).ask()

            if not selected_stack:
                return

            # Get backup location
            backup_dir = questionary.path(
                "Backup directory:",
                default="/backups/stacks",
                only_directories=True
            ).ask()

            if not backup_dir:
                return

            # Create backup
            self._perform_stack_backup(selected_stack, stacks[selected_stack], backup_dir)

        except Exception as e:
            console.print(f"[red]Error during stack backup: {str(e)}[/red]")

    def _perform_backup(self, all_containers: List[Dict], selected: List[str],
                       backup_dir: str, is_stack: bool = False):
        """Perform actual backup operation."""
        # Check if we need sudo for backup directory
        self._check_local_sudo(backup_dir)

        # Map selections back to containers
        selected_containers = []
        for selection in selected:
            container_name = selection.split(' (')[0]
            for container in all_containers:
                if container['name'] == container_name:
                    selected_containers.append(container)
                    break

        # Determine container name for directory
        if len(selected_containers) == 1:
            container_name = selected_containers[0]['name']
        else:
            container_name = f"{len(selected_containers)}_containers"

        # Create backup directory - with permission error handling
        try:
            backup_path = self.backup.create_backup_directory(backup_dir, container_name)
        except (PermissionError, OSError) as e:
            # If we get permission error and haven't enabled sudo yet, enable it and retry
            if not self.local_sudo:
                console.print(f"[yellow]Permission error detected - enabling sudo automatically[/yellow]")
                self.local_sudo = True
                self.backup = DockerBackup(self.connection, self.analyzer, local_sudo=True)
                backup_path = self.backup.create_backup_directory(backup_dir, container_name)
            else:
                raise

        console.print(f"\n[cyan]Backing up to: {backup_path}[/cyan]\n")

        # Backup each container with progress
        backup_infos = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "Backing up containers...",
                total=len(selected_containers)
            )

            for container in selected_containers:
                progress.update(
                    task,
                    description=f"Backing up {container['name']}..."
                )

                backup_info = self.backup.backup_container(
                    container['id'],
                    backup_path,
                    include_volumes=True,
                    include_compose=True
                )
                backup_infos.append(backup_info)

                progress.advance(task)

        # Generate manifest
        manifest = self.backup.generate_manifest(backup_path, {
            'containers': backup_infos,
            'host': self.connection.host
        })

        # Generate restore instructions
        generator = RestoreInstructionsGenerator(backup_path, local_sudo=self.local_sudo)
        instructions_file = generator.generate_instructions()

        # Display summary
        self._display_backup_summary(backup_path, backup_infos, instructions_file)

    def _perform_stack_backup(self, project_name: str, containers: List[Dict],
                             backup_dir: str):
        """Perform stack backup operation."""
        # Check if we need sudo for backup directory
        self._check_local_sudo(backup_dir)

        # Create backup directory with stack name - with permission error handling
        try:
            backup_path = self.backup.create_backup_directory(backup_dir, f"stack_{project_name}")
        except (PermissionError, OSError) as e:
            # If we get permission error and haven't enabled sudo yet, enable it and retry
            if not self.local_sudo:
                console.print(f"[yellow]Permission error detected - enabling sudo automatically[/yellow]")
                self.local_sudo = True
                self.backup = DockerBackup(self.connection, self.analyzer, local_sudo=True)
                backup_path = self.backup.create_backup_directory(backup_dir, f"stack_{project_name}")
            else:
                raise

        console.print(f"\n[cyan]Backing up stack '{project_name}' to: {backup_path}[/cyan]\n")

        # Backup stack
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task(description=f"Backing up stack {project_name}...", total=None)

            stack_info = self.backup.backup_stack(project_name, containers, backup_path)

        # Generate manifest
        manifest = self.backup.generate_manifest(backup_path, {
            'stack': stack_info,
            'host': self.connection.host
        })

        # Generate restore instructions
        generator = RestoreInstructionsGenerator(backup_path, local_sudo=self.local_sudo)
        instructions_file = generator.generate_instructions()

        # Display summary
        self._display_backup_summary(backup_path, [stack_info], instructions_file, is_stack=True)

    def _display_backup_summary(self, backup_path: Path, backup_infos: List[Dict],
                               instructions_file: Path, is_stack: bool = False):
        """Display backup summary."""
        console.print("\n")
        console.print(Panel.fit(
            f"[green]✓ Backup completed successfully![/green]\n\n"
            f"Location: {backup_path}\n"
            f"Restore instructions: {instructions_file}",
            title="Backup Summary"
        ))
        console.print()

    def _restore_backup_flow(self):
        """Flow for restoring from a backup."""
        try:
            console.print("\n[cyan]Restore from Backup[/cyan]")

            # Ask if user wants to browse or select from list
            browse_method = questionary.select(
                "How would you like to select a backup?",
                choices=[
                    "List available backups",
                    "Browse to backup directory manually"
                ]
            ).ask()

            if browse_method is None:
                return

            backup_path = None

            if browse_method == "List available backups":
                backup_path = self._select_from_backup_list()
                if not backup_path:
                    return
            else:
                # Manual browsing
                backup_dir = questionary.path(
                    "Path to backup directory:",
                    only_directories=True
                ).ask()

                if not backup_dir:
                    return

                backup_path = Path(backup_dir)

            # Check if we need sudo to read backup files
            from .local_sudo import LocalSudoHelper
            sudo_helper = LocalSudoHelper(use_sudo=False)
            use_local_sudo = sudo_helper.needs_sudo(backup_path)

            # Check directory exists (with sudo if needed)
            if use_local_sudo:
                import subprocess
                result = subprocess.run(['sudo', 'test', '-d', str(backup_path)], capture_output=True)
                if result.returncode != 0:
                    console.print(f"[red]Backup directory not found: {backup_dir}[/red]")
                    return
            else:
                if not backup_path.exists():
                    console.print(f"[red]Backup directory not found: {backup_dir}[/red]")
                    return

            # Check for manifest (with sudo if needed)
            manifest_file = backup_path / "manifest.json"
            if use_local_sudo:
                import subprocess
                result = subprocess.run(['sudo', 'test', '-f', str(manifest_file)], capture_output=True)
                if result.returncode != 0:
                    console.print("[red]Invalid backup: manifest.json not found[/red]")
                    return
            else:
                if not manifest_file.exists():
                    console.print("[red]Invalid backup: manifest.json not found[/red]")
                    return

            if use_local_sudo:
                console.print(f"[yellow]'{backup_path}' requires elevated privileges - automatically using sudo[/yellow]\n")

            # Check if this is a stack backup
            restore_mgr = RestoreManager(self.connection, self.analyzer, local_sudo=use_local_sudo)
            manifest = restore_mgr.read_backup_manifest(backup_path)

            if manifest and 'backup_info' in manifest:
                backup_info = manifest['backup_info']

                # Check if this is a stack backup
                if 'stack' in backup_info:
                    self._restore_stack_flow(backup_path, backup_info['stack'], restore_mgr, use_local_sudo)
                    return

            # List containers in backup (individual containers)
            containers = restore_mgr.list_containers_in_backup(backup_path)

            if not containers:
                console.print("[yellow]No containers found in backup[/yellow]")
                return

            # Display containers
            console.print(f"\n[cyan]Found {len(containers)} container(s) in backup:[/cyan]")
            table = Table()
            table.add_column("#", style="cyan")
            table.add_column("Container Name", style="green")
            table.add_column("Image", style="yellow")

            for idx, container in enumerate(containers, 1):
                table.add_row(str(idx), container['name'], container['image'])

            console.print()
            console.print(table)
            console.print()

            # Ask which containers to restore
            if len(containers) == 1:
                restore_all = True
            else:
                restore_all = questionary.confirm(
                    "Restore all containers?",
                    default=True,
                ).ask()

            selected_containers = containers

            if not restore_all:
                # Let user select specific containers
                choices = [f"{c['name']} ({c['image']})" for c in containers]
                selected = questionary.checkbox(
                    "Select containers to restore:",
                    choices=choices
                ).ask()

                if not selected:
                    return

                # Map back to containers
                selected_containers = []
                for selection in selected:
                    container_name = selection.split(' (')[0]
                    for container in containers:
                        if container['name'] == container_name:
                            selected_containers.append(container)
                            break

            # Ask for target host option
            console.print("\n[cyan]Restore Target[/cyan]")
            use_current = questionary.confirm(
                f"Restore to current host ({self.connection.host})?",
                default=True,
            ).ask()

            target_connection = self.connection
            target_analyzer = self.analyzer
            target_use_sudo = self.use_sudo

            # Show current sudo status
            if use_current:
                sudo_status = "with sudo" if self.use_sudo else "without sudo"
                console.print(f"[cyan]Target will use Docker {sudo_status}[/cyan]")

            if not use_current:
                # Connect to different host
                console.print("\n[cyan]Connect to Target Host[/cyan]")

                target_host = questionary.text("Target hostname or IP:").ask()
                if not target_host:
                    return

                # Check if we have saved credentials for this host
                target_creds = self.credential_manager.load_credentials(target_host)

                if not target_creds:
                    # Prompt for credentials
                    console.print(f"\nNo saved credentials for {target_host}")
                    username = questionary.text("Username:", default="root").ask()
                    password = questionary.password("Password:").ask()

                    target_creds = {
                        'username': username,
                        'password': password,
                        'port': 22
                    }

                # Connect to target
                target_connection = SSHConnection()
                try:
                    target_connection.connect(
                        host=target_host,
                        username=target_creds['username'],
                        password=target_creds.get('password'),
                        ssh_key_path=target_creds.get('ssh_key_path'),
                        port=target_creds.get('port', 22)
                    )
                    console.print(f"[green]✓[/green] Connected to {target_host}\n")

                    # Auto-detect sudo requirement on target
                    target_use_sudo = self._detect_sudo_for_connection(target_connection)

                    target_analyzer = DockerAnalyzer(target_connection, use_sudo=target_use_sudo)

                except Exception as e:
                    console.print(f"[red]Failed to connect to target: {str(e)}[/red]")
                    return

            # Perform restore
            self._perform_restore(selected_containers, restore_mgr, target_connection, target_analyzer)

            # Cleanup if we connected to a different host
            if not use_current:
                target_connection.disconnect()

        except Exception as e:
            console.print(f"[red]Error during restore: {str(e)}[/red]")

    def _perform_restore(self, containers: List[Dict], restore_mgr: RestoreManager,
                        target_connection: SSHConnection, target_analyzer: DockerAnalyzer):
        """
        Perform the actual restore operation.

        Args:
            containers: List of containers to restore
            restore_mgr: Restore manager instance
            target_connection: Connection to target host
            target_analyzer: Analyzer for target host
        """
        # Show sudo status for restore
        sudo_status = "with sudo" if target_analyzer.use_sudo else "without sudo"
        console.print(f"\n[cyan]Restoring {len(containers)} container(s) to {target_connection.host} ({sudo_status})...[/cyan]\n")

        # Update restore manager with target connection
        restore_mgr.connection = target_connection
        restore_mgr.analyzer = target_analyzer

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Restoring containers...", total=len(containers) * 4)

            for container in containers:
                backup_dir = container['backup_dir']
                container_name = container['name']
                image = container['image']

                # Step 1: Pull image
                progress.update(task, description=f"Pulling image {image}...")
                restore_mgr.pull_image(image)
                progress.advance(task)

                # Step 2: Restore networks
                progress.update(task, description=f"Restoring networks for {container_name}...")
                restore_mgr.restore_networks(backup_dir)
                progress.advance(task)

                # Step 3: Restore volumes
                progress.update(task, description=f"Restoring volumes for {container_name}...")
                volume_mapping = restore_mgr.restore_volumes(backup_dir)
                progress.advance(task)

                # Step 4: Create container
                progress.update(task, description=f"Creating container {container_name}...")
                try:
                    restore_mgr.restore_container(backup_dir, volume_mapping)
                    progress.advance(task)
                except Exception as e:
                    console.print(f"\n[red]✗[/red] Failed to restore {container_name}: {str(e)}")
                    progress.advance(task)
                    continue

        console.print("\n")
        console.print(Panel.fit(
            f"[green]✓ Restore completed![/green]\n\n"
            f"Restored {len(containers)} container(s)\n"
            f"Target host: {target_connection.host}",
            title="Restore Summary"
        ))
        console.print()

    def _select_from_backup_list(self) -> Optional[Path]:
        """
        Scan for and display available backups for selection.

        Returns:
            Path to selected backup or None
        """
        console.print("\n[cyan]Scanning for backups...[/cyan]")

        # Check if we need sudo to read backup directories
        local_sudo_helper = LocalSudoHelper(use_sudo=False)
        use_local_sudo = False

        # Check common backup locations - prioritize /backups
        common_dirs = ["/backups", str(Path.home() / "backups"), "./backups"]
        for dir_path in common_dirs:
            path = Path(dir_path)
            if path.exists() and local_sudo_helper.needs_sudo(path):
                console.print(f"[yellow]'{dir_path}' requires elevated privileges - automatically using sudo[/yellow]")
                use_local_sudo = True
                break

        # Scan for backups
        scanner = BackupScanner(use_sudo=use_local_sudo)
        backups = scanner.find_backups()

        if not backups:
            console.print("\n[yellow]No backups found in common locations.[/yellow]")
            console.print("Common locations checked:")
            for location in scanner.get_default_backup_dirs():
                console.print(f"  - {location}")
            console.print("\nTip: Use 'Browse to backup directory manually' to specify a custom location.")
            return None

        # Display backups in table
        console.print(f"\n[cyan]Found {len(backups)} backup(s):[/cyan]\n")

        table = Table()
        table.add_column("#", style="cyan", width=4)
        table.add_column("Backup Name", style="green")
        table.add_column("Date/Time", style="yellow")
        table.add_column("Containers", style="blue")
        table.add_column("Source Host", style="magenta")
        table.add_column("Size", style="white")

        for idx, backup in enumerate(backups, 1):
            container_info = f"{backup['container_count']} container(s)"
            if backup['containers']:
                # Show first container name
                first_container = backup['containers'][0]
                if len(first_container) > 20:
                    first_container = first_container[:17] + "..."
                container_info = f"{backup['container_count']}: {first_container}"

            table.add_row(
                str(idx),
                backup['name'],
                backup['timestamp'],
                container_info,
                backup['source_host'],
                backup['size']
            )

        console.print(table)
        console.print()

        # Let user select
        choices = [f"{idx}. {b['name']} ({b['timestamp']})"
                   for idx, b in enumerate(backups, 1)]
        choices.append("Cancel")

        selection = questionary.select(
            "Select a backup to restore:",
            choices=choices
        ).ask()

        if selection is None or selection == "Cancel":
            return None

        # Extract index from selection
        selected_idx = int(selection.split('.')[0]) - 1
        selected_backup = backups[selected_idx]

        return Path(selected_backup['path'])

    def _delete_container_flow(self):
        """Flow for deleting containers with all volumes and resources."""
        try:
            console.print("\n[cyan]Delete Container[/cyan]")
            console.print("[yellow]⚠  This will permanently delete the container and ALL associated volumes![/yellow]\n")

            # Get all containers
            containers = self.analyzer.list_containers()

            if not containers:
                console.print("[yellow]No containers found.[/yellow]")
                return

            # Let user select containers to delete
            choices = [
                f"{c['name']} ({c['image']}) - {c['status']}"
                for c in containers
            ]

            selected = questionary.checkbox(
                "Select containers to DELETE (use Space to select, Enter to confirm):",
                choices=choices
            ).ask()

            if not selected or len(selected) == 0:
                console.print("[yellow]No containers selected.[/yellow]")
                return

            # Find selected container objects
            selected_containers = []
            for choice in selected:
                container_name = choice.split(' (')[0]
                for c in containers:
                    if c['name'] == container_name:
                        selected_containers.append(c)
                        break

            # Confirm deletion
            console.print(f"\n[red]⚠  WARNING: You are about to delete {len(selected_containers)} container(s):[/red]")
            for c in selected_containers:
                console.print(f"  - {c['name']}")
            console.print(f"\n[red]This will also delete ALL volumes attached to these containers![/red]")

            confirm = questionary.confirm(
                "Are you absolutely sure you want to proceed?",
                default=False
            ).ask()

            if not confirm:
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return

            # Perform deletion
            self._perform_deletion(selected_containers)

        except Exception as e:
            console.print(f"[red]Error during deletion: {str(e)}[/red]")

    def _perform_deletion(self, containers: List[Dict]):
        """
        Perform the actual container deletion.

        Args:
            containers: List of containers to delete
        """
        sudo_prefix = "sudo " if self.analyzer.use_sudo else ""
        deleted_count = 0
        failed_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Deleting containers...", total=len(containers))

            for container in containers:
                container_id = container['id']
                container_name = container['name']

                try:
                    progress.update(task, description=f"Deleting {container_name}...")

                    # Get volume information before deletion
                    volumes = self.analyzer.get_container_volumes(container_id)
                    volume_names = []

                    for volume in volumes:
                        if volume.get('type') == 'volume':
                            # Extract volume name from source
                            source = volume.get('source', '')
                            if source:
                                volume_names.append(source)

                    # Stop container if running
                    if container['state'] == 'running':
                        stop_cmd = f"{sudo_prefix}docker stop {container_id}"
                        self.connection.execute_command(stop_cmd, timeout=30)

                    # Remove container
                    rm_cmd = f"{sudo_prefix}docker rm {container_id}"
                    stdout, stderr, exit_code = self.connection.execute_command(rm_cmd)

                    if exit_code != 0:
                        raise RuntimeError(f"Failed to remove container: {stderr}")

                    # Remove associated volumes
                    for volume_name in volume_names:
                        vol_rm_cmd = f"{sudo_prefix}docker volume rm {volume_name}"
                        vol_stdout, vol_stderr, vol_exit = self.connection.execute_command(vol_rm_cmd)

                        if vol_exit != 0 and "in use" not in vol_stderr:
                            console.print(f"\n[yellow]Warning: Could not remove volume {volume_name}: {vol_stderr}[/yellow]")

                    deleted_count += 1
                    console.print(f"\n[green]✓[/green] Deleted {container_name} and {len(volume_names)} volume(s)")

                except Exception as e:
                    failed_count += 1
                    console.print(f"\n[red]✗[/red] Failed to delete {container_name}: {str(e)}")

                progress.advance(task)

        # Summary
        console.print("\n")
        console.print(Panel.fit(
            f"[green]Deletion completed![/green]\n\n"
            f"Successfully deleted: {deleted_count} container(s)\n"
            f"Failed: {failed_count} container(s)",
            title="Deletion Summary"
        ))
        console.print()

    def _restore_stack_flow(self, backup_path: Path, stack_info: Dict,
                           restore_mgr: RestoreManager, use_local_sudo: bool):
        """
        Flow for restoring a Docker Compose stack.

        Args:
            backup_path: Path to stack backup
            stack_info: Stack information from manifest
            restore_mgr: Restore manager instance
            use_local_sudo: Whether to use sudo for local operations
        """
        try:
            project_name = stack_info.get('project_name', 'unknown')
            container_count = len(stack_info.get('containers', []))

            console.print(f"\n[cyan]Stack Backup Detected[/cyan]")
            console.print(f"Project: [green]{project_name}[/green]")
            console.print(f"Containers: [yellow]{container_count}[/yellow]\n")

            # Ask if user wants to restore to current host or different host
            console.print("[cyan]Restore Target[/cyan]")
            use_current = questionary.confirm(
                f"Restore to current host ({self.connection.host})?",
                default=True
            ).ask()

            if use_current is None:
                return

            target_connection = self.connection
            target_analyzer = self.analyzer

            if not use_current:
                # Connect to different host
                console.print("\n[cyan]Connect to Target Host[/cyan]")

                target_host = questionary.text("Target hostname or IP:").ask()
                if not target_host:
                    return

                # Try to load saved credentials for target
                target_creds = self.credential_manager.load_credentials(target_host, self.master_password)

                if not target_creds:
                    console.print(f"[yellow]No saved credentials for {target_host}[/yellow]")
                    # Prompt for credentials
                    target_creds = {
                        'username': questionary.text("Username:").ask(),
                        'password': questionary.password("Password:").ask(),
                        'port': int(questionary.text("Port:", default="22").ask())
                    }

                try:
                    target_connection = SSHConnection()
                    target_connection.connect(
                        host=target_host,
                        username=target_creds['username'],
                        password=target_creds.get('password'),
                        ssh_key_path=target_creds.get('ssh_key_path'),
                        port=target_creds.get('port', 22)
                    )
                    console.print(f"[green]✓[/green] Connected to {target_host}\n")

                    # Auto-detect sudo requirement on target
                    target_use_sudo = self._detect_sudo_for_connection(target_connection)
                    target_analyzer = DockerAnalyzer(target_connection, use_sudo=target_use_sudo)

                except Exception as e:
                    console.print(f"[red]Failed to connect to target: {str(e)}[/red]")
                    return

            # Show what will be restored
            console.print(f"[cyan]Target will use Docker {'with sudo' if target_analyzer.use_sudo else 'without sudo'}[/cyan]\n")

            confirm = questionary.confirm(
                f"Restore stack '{project_name}' with {container_count} containers?",
                default=True
            ).ask()

            if not confirm:
                console.print("[yellow]Restore cancelled.[/yellow]")
                return

            # Perform stack restore
            self._perform_stack_restore(backup_path, stack_info, restore_mgr,
                                       target_connection, target_analyzer, use_local_sudo)

            # Cleanup if we connected to a different host
            if not use_current:
                target_connection.disconnect()

        except Exception as e:
            console.print(f"[red]Error during stack restore: {str(e)}[/red]")

    def _perform_stack_restore(self, backup_path: Path, stack_info: Dict,
                              restore_mgr: RestoreManager,
                              target_connection: SSHConnection,
                              target_analyzer: DockerAnalyzer,
                              use_local_sudo: bool):
        """
        Perform the actual stack restore operation.

        Args:
            backup_path: Path to stack backup
            stack_info: Stack information from manifest
            restore_mgr: Restore manager instance
            target_connection: Connection to target host
            target_analyzer: Analyzer for target host
            use_local_sudo: Whether to use sudo for local operations
        """
        project_name = stack_info.get('project_name', 'unknown')
        sudo_prefix = "sudo " if target_analyzer.use_sudo else ""

        console.print(f"\n[cyan]Restoring stack '{project_name}' to {target_connection.host}...[/cyan]\n")

        # Update restore manager with target connection
        restore_mgr.connection = target_connection
        restore_mgr.analyzer = target_analyzer

        # Step 1: Check if docker-compose file exists
        from .local_sudo import LocalSudoHelper
        local_sudo_helper = LocalSudoHelper(use_sudo=use_local_sudo)

        # Find docker-compose file
        # Stack structure: backup_path / project_name / docker-compose.yml (or in container subdirs)
        stack_backup_dir_for_compose = backup_path / project_name
        compose_file = None

        # First, check if docker-compose.yml is in the stack directory itself
        potential_compose_root = stack_backup_dir_for_compose / "docker-compose.yml"
        if use_local_sudo:
            import subprocess
            result = subprocess.run(['sudo', 'test', '-f', str(potential_compose_root)],
                                  capture_output=True)
            if result.returncode == 0:
                compose_file = potential_compose_root
        else:
            if potential_compose_root.exists():
                compose_file = potential_compose_root

        # If not found in root, check in container directories
        if not compose_file:
            for container in stack_info.get('containers', []):
                if container.get('has_compose'):
                    container_name = container.get('container_name')
                    potential_compose = stack_backup_dir_for_compose / container_name / "docker-compose.yml"

                    if use_local_sudo:
                        import subprocess
                        result = subprocess.run(['sudo', 'test', '-f', str(potential_compose)],
                                              capture_output=True)
                        if result.returncode == 0:
                            compose_file = potential_compose
                            break
                    else:
                        if potential_compose.exists():
                            compose_file = potential_compose
                            break

        if not compose_file:
            console.print("[yellow]No docker-compose.yml found in backup. Restoring containers individually...[/yellow]\n")

        # Step 2: Restore all containers in the stack
        # Note: Stack backups have structure: backup_path / project_name / container_name /
        stack_backup_dir = backup_path / project_name

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            containers = stack_info.get('containers', [])
            task = progress.add_task("Restoring stack...", total=len(containers) * 4)

            for container_info in containers:
                container_name = container_info.get('container_name')
                container_dir = stack_backup_dir / container_name

                try:
                    # Restore networks
                    progress.update(task, description=f"Restoring networks for {container_name}...")
                    restore_mgr.restore_networks(container_dir)
                    progress.advance(task)

                    # Restore volumes
                    progress.update(task, description=f"Restoring volumes for {container_name}...")
                    volume_mapping = restore_mgr.restore_volumes(container_dir)
                    progress.advance(task)

                    # Pull image
                    progress.update(task, description=f"Pulling image for {container_name}...")
                    image = container_info.get('image', 'unknown')
                    restore_mgr.pull_image(image)
                    progress.advance(task)

                    # Create container
                    progress.update(task, description=f"Creating container {container_name}...")
                    restore_mgr.restore_container(container_dir, volume_mapping)
                    progress.advance(task)

                except Exception as e:
                    console.print(f"\n[red]✗[/red] Failed to restore {container_name}: {str(e)}")
                    progress.advance(task, advance=4 - (progress.tasks[0].completed % 4))

        # Step 3: If docker-compose file exists, upload and use it
        if compose_file:
            try:
                console.print(f"\n[cyan]Deploying stack with docker-compose...[/cyan]")

                # Create remote temp directory for compose file
                remote_temp_dir = f'/tmp/dockerbak_stack_{project_name}'
                mkdir_cmd = f'{sudo_prefix}mkdir -p {remote_temp_dir}'
                target_connection.execute_command(mkdir_cmd)

                # Upload compose file
                remote_compose = f'{remote_temp_dir}/docker-compose.yml'

                if use_local_sudo:
                    import tempfile
                    import subprocess
                    import os

                    # Copy to temp location for upload
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.yml') as tmp:
                        temp_upload_path = tmp.name

                    subprocess.run(['sudo', 'cp', str(compose_file), temp_upload_path], check=True)
                    subprocess.run(['sudo', 'chown', str(os.getuid()), temp_upload_path], check=True)

                    try:
                        target_connection.sftp.put(temp_upload_path, remote_compose)
                    finally:
                        os.unlink(temp_upload_path)
                else:
                    target_connection.sftp.put(str(compose_file), remote_compose)

                # Deploy with docker-compose
                compose_cmd = f'cd {remote_temp_dir} && {sudo_prefix}docker-compose up -d'
                stdout, stderr, exit_code = target_connection.execute_command(compose_cmd, timeout=300)

                if exit_code == 0:
                    console.print(f"[green]✓[/green] Stack deployed successfully with docker-compose")
                else:
                    console.print(f"[yellow]Warning: docker-compose deployment had issues: {stderr}[/yellow]")

                # Cleanup
                cleanup_cmd = f'{sudo_prefix}rm -rf {remote_temp_dir}'
                target_connection.execute_command(cleanup_cmd)

            except Exception as e:
                console.print(f"[yellow]Warning: Could not deploy with docker-compose: {str(e)}[/yellow]")
                console.print("[yellow]Containers were restored individually.[/yellow]")

        # Summary
        console.print("\n")
        console.print(Panel.fit(
            f"[green]✓ Stack restore completed![/green]\n\n"
            f"Stack: {project_name}\n"
            f"Containers: {len(containers)}\n"
            f"Target host: {target_connection.host}",
            title="Stack Restore Summary"
        ))
        console.print()

    def _manage_hosts_flow(self):
        """Interactive flow for managing saved hosts."""
        while True:
            # Get all saved hosts with their display names
            hosts_with_names = self.credential_manager.list_hosts_with_names()

            if not hosts_with_names:
                console.print("[yellow]No saved hosts found.[/yellow]")
                questionary.press_any_key_to_continue("Press any key to continue...").ask()
                return

            # Build menu choices
            choices = []
            for host, display_name in hosts_with_names.items():
                choices.append({
                    'name': display_name,
                    'value': host
                })
            choices.append({'name': '← Back to main menu', 'value': 'back'})

            # Select host to manage
            selected_host = questionary.select(
                "Select a host to manage:",
                choices=choices
            ).ask()

            if selected_host == 'back' or selected_host is None:
                return

            # Show management options for selected host
            current_display = hosts_with_names[selected_host]

            action = questionary.select(
                f"Manage: {current_display}",
                choices=[
                    {'name': 'Rename (set vanity name)', 'value': 'rename'},
                    {'name': 'Delete host', 'value': 'delete'},
                    {'name': '← Back', 'value': 'back'}
                ]
            ).ask()

            if action == 'rename':
                self._rename_host(selected_host)
            elif action == 'delete':
                self._delete_host(selected_host, current_display)
            elif action is None or action == 'back':
                continue

    def _rename_host(self, host: str):
        """Rename a host with a vanity name."""
        console.print(f"\n[cyan]Renaming host: {host}[/cyan]")
        console.print("[dim]Enter a friendly name for this host (leave empty to remove vanity name)[/dim]\n")

        vanity_name = questionary.text(
            "Vanity name:",
            default=""
        ).ask()

        if vanity_name is None:
            return

        # Empty string means remove vanity name
        if vanity_name.strip() == "":
            vanity_name = None

        # Update the credentials
        creds = self.credential_manager.load_credentials(host)
        if creds:
            self.credential_manager.save_credentials(
                host=host,
                username=creds['username'],
                password=creds['password'],
                ssh_key_path=creds['ssh_key_path'],
                port=creds['port'],
                vanity_name=vanity_name
            )

            if vanity_name:
                console.print(f"[green]✓[/green] Host renamed to: {vanity_name}")
            else:
                console.print(f"[green]✓[/green] Vanity name removed")
        else:
            console.print("[red]Error: Could not load host credentials[/red]")

        questionary.press_any_key_to_continue("\nPress any key to continue...").ask()

    def _delete_host(self, host: str, display_name: str):
        """Delete a saved host."""
        console.print(f"\n[yellow]⚠ Warning: You are about to delete saved credentials for:[/yellow]")
        console.print(f"  {display_name}\n")

        confirm = questionary.confirm(
            "Are you sure you want to delete this host?",
            default=False
        ).ask()

        if confirm:
            if self.credential_manager.delete_credentials(host):
                console.print(f"[green]✓[/green] Host deleted successfully")
            else:
                console.print("[red]Error: Could not delete host[/red]")
        else:
            console.print("[dim]Deletion cancelled[/dim]")

        questionary.press_any_key_to_continue("\nPress any key to continue...").ask()
