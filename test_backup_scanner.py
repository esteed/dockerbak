#!/usr/bin/env python3
"""
Test script for backup scanner functionality.
"""

import sys
from pathlib import Path
from src.backup_scanner import BackupScanner
from rich.console import Console
from rich.table import Table

console = Console()


def test_scanner():
    """Test the backup scanner."""
    console.print("\n[bold blue]Testing Backup Scanner[/bold blue]\n")

    # Test 1: Check if scanner instantiates
    console.print("[cyan]Test 1: Scanner Instantiation[/cyan]")
    try:
        scanner = BackupScanner(use_sudo=False)
        console.print("[green]✓[/green] Scanner created successfully\n")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create scanner: {e}\n")
        return False

    # Test 2: Get default directories
    console.print("[cyan]Test 2: Default Backup Directories[/cyan]")
    default_dirs = scanner.get_default_backup_dirs()
    console.print(f"[green]✓[/green] Default directories: {len(default_dirs)}")
    for d in default_dirs:
        exists = Path(d).exists()
        status = "[green]exists[/green]" if exists else "[yellow]not found[/yellow]"
        console.print(f"  - {d}: {status}")
    console.print()

    # Test 3: Scan for backups (without sudo)
    console.print("[cyan]Test 3: Scanning for Backups (no sudo)[/cyan]")
    try:
        backups = scanner.find_backups()
        console.print(f"[green]✓[/green] Scan completed: {len(backups)} backup(s) found\n")

        if backups:
            # Display results
            console.print("[cyan]Found Backups:[/cyan]\n")

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

            # Show details of first backup
            console.print("[cyan]Details of first backup:[/cyan]")
            first = backups[0]
            console.print(f"  Path: {first['path']}")
            console.print(f"  Name: {first['name']}")
            console.print(f"  Timestamp: {first['timestamp']}")
            console.print(f"  Container Count: {first['container_count']}")
            console.print(f"  Containers: {', '.join(first['containers'])}")
            console.print(f"  Source Host: {first['source_host']}")
            console.print(f"  Size: {first['size']}")
            console.print()

        else:
            console.print("[yellow]⚠[/yellow] No backups found in default locations")
            console.print("\nThis could be because:")
            console.print("  1. No backups have been created yet")
            console.print("  2. Backups are in a non-standard location")
            console.print("  3. Backups require sudo to access")
            console.print()

    except Exception as e:
        console.print(f"[red]✗[/red] Scan failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Check if /backups exists and needs sudo
    console.print("[cyan]Test 4: Checking /backups Access[/cyan]")
    backups_dir = Path("/backups")
    if backups_dir.exists():
        console.print(f"[green]✓[/green] /backups directory exists")

        # Check if readable
        try:
            list(backups_dir.iterdir())
            console.print(f"[green]✓[/green] /backups is readable (no sudo needed)")
        except PermissionError:
            console.print(f"[yellow]⚠[/yellow] /backups requires elevated privileges")
            console.print(f"[yellow]→[/yellow] Run with sudo scanning to access these backups")

            # Offer to test with sudo
            console.print("\n[cyan]Would you like to test with sudo? (y/n)[/cyan]")
            choice = input("> ").strip().lower()

            if choice == 'y':
                console.print("\n[cyan]Scanning with sudo...[/cyan]")
                try:
                    sudo_scanner = BackupScanner(use_sudo=True)
                    sudo_backups = sudo_scanner.scan_directory("/backups")
                    console.print(f"[green]✓[/green] Found {len(sudo_backups)} backup(s) with sudo")

                    if sudo_backups:
                        for idx, backup in enumerate(sudo_backups, 1):
                            console.print(f"  {idx}. {backup['name']} ({backup['timestamp']})")
                except Exception as e:
                    console.print(f"[red]✗[/red] Sudo scan failed: {e}")
    else:
        console.print(f"[yellow]⚠[/yellow] /backups directory does not exist")

    console.print()

    # Test 5: Validate a specific backup (if any exist)
    if backups:
        console.print("[cyan]Test 5: Validating Backup Structure[/cyan]")
        first_backup_path = Path(backups[0]['path'])

        # Check for required files
        checks = [
            ("manifest.json", first_backup_path / "manifest.json"),
        ]

        # Check for container directories
        container_dirs = [d for d in first_backup_path.iterdir() if d.is_dir()]
        if container_dirs:
            first_container_dir = container_dirs[0]
            checks.extend([
                ("metadata.json", first_container_dir / "metadata.json"),
                ("networks.json", first_container_dir / "networks.json"),
            ])

        all_good = True
        for name, path in checks:
            if path.exists():
                console.print(f"  [green]✓[/green] {name} exists")
            else:
                console.print(f"  [red]✗[/red] {name} missing")
                all_good = False

        if all_good:
            console.print("\n[green]✓[/green] Backup structure is valid")
        else:
            console.print("\n[yellow]⚠[/yellow] Some backup files are missing")

        console.print()

    # Summary
    console.print("\n" + "="*60)
    console.print("[bold green]Backup Scanner Test Summary[/bold green]")
    console.print("="*60)
    console.print(f"Scanner: [green]Working[/green]")
    console.print(f"Backups Found: [cyan]{len(backups)}[/cyan]")
    console.print(f"Default Locations Checked: [cyan]{len(default_dirs)}[/cyan]")
    console.print("="*60 + "\n")

    return True


if __name__ == "__main__":
    try:
        success = test_scanner()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Test interrupted by user[/yellow]\n")
        sys.exit(130)
