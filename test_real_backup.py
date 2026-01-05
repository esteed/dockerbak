#!/usr/bin/env python3
"""
Real backup test to /backups/containers/ with automatic sudo handling
"""
import sys
import getpass
from pathlib import Path
from src.credentials import CredentialManager
from src.connection import SSHConnection
from src.docker_analyzer import DockerAnalyzer
from src.backup import DockerBackup
from src.local_sudo import LocalSudoHelper
from src.restore import RestoreInstructionsGenerator
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def main():
    console.print("\n[bold cyan]Real Backup Test - /backups/containers/[/bold cyan]\n")
    
    # Load saved credentials
    console.print("[cyan]Loading saved credentials...[/cyan]")
    cred_manager = CredentialManager()
    
    master_password = getpass.getpass("Master password: ")
    
    try:
        creds = cred_manager.load_credentials("192.168.1.35", master_password)
        if creds:
            creds['host'] = "192.168.1.35"
            console.print("[green]✓[/green] Credentials loaded\n")
        else:
            console.print("[red]No credentials found for 192.168.1.35[/red]")
            return 1
    except Exception as e:
        console.print(f"[red]Failed to load credentials: {e}[/red]")
        return 1
    
    # Connect
    console.print("[cyan]Connecting to 192.168.1.35...[/cyan]")
    connection = SSHConnection()
    
    try:
        connection.connect(
            host=creds['host'],
            username=creds['username'],
            password=creds.get('password'),
            ssh_key_path=creds.get('ssh_key_path'),
            port=creds['port']
        )
        console.print(f"[green]✓[/green] Connected to {creds['host']}\n")
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        return 1
    
    # Auto-detect Docker sudo
    console.print("[cyan]Detecting Docker sudo requirement...[/cyan]")
    stdout, stderr, exit_code = connection.execute_command("docker ps -q", timeout=10)
    use_sudo = False
    
    if exit_code != 0 and ("permission denied" in stderr.lower() or "connect to the docker daemon" in stderr.lower()):
        console.print("[yellow]Docker requires sudo - testing...[/yellow]")
        stdout, stderr, exit_code = connection.execute_command("sudo docker ps -q", timeout=10)
        if exit_code == 0:
            use_sudo = True
            console.print("[green]✓[/green] Docker sudo confirmed\n")
    else:
        console.print("[green]✓[/green] Docker accessible without sudo\n")
    
    # Initialize analyzer
    console.print("[cyan]Analyzing Docker environment...[/cyan]")
    analyzer = DockerAnalyzer(connection, use_sudo=use_sudo)
    containers = analyzer.list_containers()
    console.print(f"[green]✓[/green] Found {len(containers)} containers\n")
    
    # Find Smokeping container
    smokeping = None
    for container in containers:
        if container['name'] == 'Smokeping':
            smokeping = container
            break
    
    if not smokeping:
        console.print("[yellow]Smokeping container not found, using first container[/yellow]")
        smokeping = containers[0]
    
    console.print(f"[cyan]Selected container:[/cyan] {smokeping['name']}")
    console.print(f"[cyan]Image:[/cyan] {smokeping['image']}\n")
    
    # Check if /backups/containers/ needs sudo
    backup_dir = "/backups/containers/"
    console.print(f"[cyan]Checking permissions for {backup_dir}...[/cyan]")
    
    sudo_helper = LocalSudoHelper(use_sudo=False)
    needs_sudo = sudo_helper.needs_sudo(Path(backup_dir))
    
    if needs_sudo:
        console.print(f"[yellow]'{backup_dir}' requires elevated privileges - automatically using sudo[/yellow]\n")
        local_sudo = True
    else:
        console.print(f"[green]'{backup_dir}' is writable without sudo[/green]\n")
        local_sudo = False
    
    # Create backup
    console.print("[cyan]Creating backup...[/cyan]")
    backup = DockerBackup(connection, analyzer, local_sudo=local_sudo)
    
    # Create backup directory with error handling
    try:
        backup_path = backup.create_backup_directory(backup_dir, smokeping['name'])
        console.print(f"[green]✓[/green] Created backup directory: {backup_path}\n")
    except (PermissionError, OSError) as e:
        if not local_sudo:
            console.print(f"[yellow]Permission error - enabling sudo and retrying...[/yellow]")
            local_sudo = True
            backup = DockerBackup(connection, analyzer, local_sudo=True)
            backup_path = backup.create_backup_directory(backup_dir, smokeping['name'])
            console.print(f"[green]✓[/green] Created backup directory with sudo: {backup_path}\n")
        else:
            console.print(f"[red]Failed even with sudo: {e}[/red]")
            return 1
    
    # Backup container
    console.print(f"[cyan]Backing up container '{smokeping['name']}'...[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(description="Backing up container...", total=None)
        
        backup_info = backup.backup_container(
            container_id=smokeping['id'],
            output_dir=backup_path,
            include_volumes=True,
            include_compose=True
        )
        
        progress.update(task, completed=1)
    
    console.print(f"[green]✓[/green] Container backup complete")
    console.print(f"   Files: {len(backup_info['files'])}")
    if 'volume_count' in backup_info:
        console.print(f"   Volumes: {backup_info['volume_count']}\n")
    
    # Generate manifest
    console.print("[cyan]Generating manifest...[/cyan]")
    manifest_info = {
        'timestamp': backup_info['timestamp'],
        'host': creds['host'],
        'containers': [backup_info]
    }
    manifest_file = backup.generate_manifest(backup_path, manifest_info)
    console.print(f"[green]✓[/green] Manifest created\n")
    
    # Generate restore instructions
    console.print("[cyan]Generating restore instructions...[/cyan]")
    generator = RestoreInstructionsGenerator(backup_path, local_sudo=local_sudo)
    instructions_file = generator.generate_instructions()
    console.print(f"[green]✓[/green] Instructions created\n")
    
    # Verify files
    console.print("[cyan]Verifying backup files...[/cyan]")
    import subprocess
    result = subprocess.run(
        ['sudo', 'find', str(backup_path), '-type', 'f'] if local_sudo else ['find', str(backup_path), '-type', 'f'],
        capture_output=True,
        text=True
    )
    
    files = [f for f in result.stdout.strip().split('\n') if f]
    for file in files:
        console.print(f"  [green]✓[/green] {Path(file).name}")
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold green]BACKUP SUCCESSFUL![/bold green]")
    console.print("="*60)
    console.print(f"Location: {backup_path}")
    console.print(f"Container: {smokeping['name']}")
    console.print(f"Files: {len(files)}")
    console.print(f"Local Sudo: {'Yes' if local_sudo else 'No'}")
    console.print(f"Docker Sudo: {'Yes' if use_sudo else 'No'}")
    console.print("="*60)
    
    connection.disconnect()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
