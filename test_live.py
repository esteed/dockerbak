#!/usr/bin/env python3
"""
Live test script for Dockerbak with real Docker host.
This script tests connectivity and Docker availability before launching the full CLI.
"""

import sys
from pathlib import Path
import getpass

from src.credentials import CredentialManager
from src.connection import SSHConnection
from src.docker_analyzer import DockerAnalyzer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def test_connection(host, username, password, ssh_key_path, port):
    """Test SSH connection to Docker host."""
    console.print("\n[cyan]Testing SSH Connection[/cyan]")

    try:
        conn = SSHConnection()
        conn.connect(
            host=host,
            username=username,
            password=password,
            ssh_key_path=ssh_key_path,
            port=port
        )

        console.print(f"[green]✓[/green] Connected to {host}")

        # Auto-detect sudo requirement
        console.print("\n[cyan]Testing Docker Availability[/cyan]")
        console.print("Auto-detecting sudo requirement...")

        use_sudo = False
        stdout, stderr, exit_code = conn.execute_command("docker ps -q", timeout=10)

        if exit_code != 0 and ("permission denied" in stderr.lower() or "connect to the docker daemon socket" in stderr.lower()):
            console.print("[yellow]⚠[/yellow] Docker requires sudo, testing...")
            stdout, stderr, exit_code = conn.execute_command("sudo docker ps -q", timeout=10)
            if exit_code == 0:
                use_sudo = True
                console.print("[green]✓[/green] Sudo access confirmed")

        if use_sudo:
            console.print("[yellow]Using sudo for Docker commands[/yellow]")
        else:
            console.print("[green]Docker accessible without sudo[/green]")

        analyzer = DockerAnalyzer(conn, use_sudo=use_sudo)

        if not analyzer.check_docker_available():
            console.print("[red]✗[/red] Docker not available on remote host")
            conn.disconnect()
            return False

        version_info = analyzer.get_docker_version()
        server_version = version_info.get('Server', {}).get('Version', 'Unknown')
        console.print(f"[green]✓[/green] Docker version: {server_version}")

        # List containers
        console.print("\n[cyan]Listing Containers[/cyan]")
        containers = analyzer.list_containers()

        if not containers:
            console.print("[yellow]⚠[/yellow] No containers found on host")
        else:
            table = Table(title=f"Found {len(containers)} container(s)")
            table.add_column("Name", style="cyan")
            table.add_column("Image", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("State")

            for container in containers[:10]:  # Show first 10
                table.add_row(
                    container['name'],
                    container['image'],
                    container['status'],
                    container['state']
                )

            console.print()
            console.print(table)

        # List stacks
        console.print("\n[cyan]Listing Docker Compose Stacks[/cyan]")
        stacks = analyzer.list_stacks()

        if not stacks:
            console.print("[yellow]⚠[/yellow] No Docker Compose stacks found")
        else:
            for project_name, stack_containers in stacks.items():
                console.print(f"[green]✓[/green] Stack: {project_name} ({len(stack_containers)} containers)")

        # Test summary
        console.print("\n" + "="*60)
        console.print(Panel.fit(
            f"[green]✓ Connection Test Successful![/green]\n\n"
            f"Host: {host}\n"
            f"Docker: {server_version}\n"
            f"Containers: {len(containers)}\n"
            f"Stacks: {len(stacks)}",
            title="Test Results"
        ))
        console.print("="*60)

        conn.disconnect()
        return True

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
        return False


def main():
    """Main test flow."""
    console.print("\n[bold blue]Dockerbak Live Test[/bold blue]")
    console.print("This will test connectivity to your Docker host.\n")

    # Get connection details
    console.print("[cyan]Enter Docker Host Details:[/cyan]\n")

    host = input("Hostname or IP: ").strip()
    if not host:
        console.print("[red]Hostname required[/red]")
        return 1

    username = input(f"Username [{getpass.getuser()}]: ").strip() or getpass.getuser()
    port = input("Port [22]: ").strip() or "22"
    port = int(port)

    auth_method = input("Authentication (1=Password, 2=SSH Key) [1]: ").strip() or "1"

    password = None
    ssh_key_path = None

    if auth_method == "1":
        password = getpass.getpass("Password: ")
    else:
        default_key = str(Path.home() / ".ssh" / "id_rsa")
        ssh_key_path = input(f"SSH Key Path [{default_key}]: ").strip() or default_key

    # Test connection will auto-detect sudo
    success = test_connection(host, username, password, ssh_key_path, port)

    if success:
        console.print("\n[cyan]Would you like to launch the full Dockerbak CLI? (y/n)[/cyan]")
        choice = input("> ").strip().lower()

        if choice == 'y':
            console.print("\n[green]Launching Dockerbak...[/green]\n")
            from src.cli import DockerBakCLI
            cli = DockerBakCLI()
            return cli.run()
        else:
            console.print("\n[green]Test completed successfully![/green]")
            return 0
    else:
        console.print("\n[red]Connection test failed. Please check your settings.[/red]")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
