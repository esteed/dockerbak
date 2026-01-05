"""
Backup scanner for discovering available backups.
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class BackupScanner:
    """Scans directories for valid Docker backups."""

    def __init__(self, use_sudo: bool = False):
        """
        Initialize backup scanner.

        Args:
            use_sudo: Whether to use sudo for reading directories
        """
        self.use_sudo = use_sudo

    def scan_directory(self, base_dir: str) -> List[Dict]:
        """
        Scan a directory for valid backups.

        Args:
            base_dir: Base directory to scan

        Returns:
            List of backup information dictionaries
        """
        backups = []
        base_path = Path(base_dir)

        try:
            # Check if directory exists and is readable
            if not self._can_read_directory(base_path):
                return []

            # Get all subdirectories
            subdirs = self._list_subdirectories(base_path)

            for subdir in subdirs:
                backup_info = self._analyze_backup(subdir)
                if backup_info:
                    backups.append(backup_info)

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        except Exception as e:
            print(f"Error scanning directory {base_dir}: {str(e)}")

        return backups

    def _can_read_directory(self, path: Path) -> bool:
        """
        Check if directory can be read.

        Args:
            path: Directory path

        Returns:
            True if readable
        """
        if self.use_sudo:
            # Test with sudo
            result = subprocess.run(
                ['sudo', 'test', '-d', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.exists() and path.is_dir()

    def _list_subdirectories(self, path: Path) -> List[Path]:
        """
        List all subdirectories in a path.

        Args:
            path: Path to search

        Returns:
            List of subdirectory paths
        """
        subdirs = []

        try:
            if self.use_sudo:
                # Use sudo to list directories
                result = subprocess.run(
                    ['sudo', 'find', str(path), '-maxdepth', '1', '-type', 'd'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line and line != str(path):
                            subdirs.append(Path(line))
            else:
                subdirs = [d for d in path.iterdir() if d.is_dir()]

        except Exception as e:
            print(f"Error listing directories: {str(e)}")

        return subdirs

    def _analyze_backup(self, backup_dir: Path) -> Optional[Dict]:
        """
        Analyze a backup directory and extract metadata.

        Args:
            backup_dir: Path to backup directory

        Returns:
            Backup information dictionary or None if invalid
        """
        manifest_path = backup_dir / "manifest.json"

        # Check if manifest exists
        if not self._file_exists(manifest_path):
            return None

        try:
            # Read manifest
            manifest_content = self._read_file(manifest_path)
            manifest = json.loads(manifest_content)

            backup_info = manifest.get('backup_info', {})

            # Extract container information
            containers = []
            container_count = 0

            if 'containers' in backup_info:
                # Individual container(s) backup
                for container in backup_info['containers']:
                    containers.append(container.get('container_name', 'Unknown'))
                container_count = len(backup_info['containers'])
            elif 'stack' in backup_info:
                # Stack backup
                stack = backup_info['stack']
                containers.append(f"Stack: {stack.get('project_name', 'Unknown')}")
                container_count = len(stack.get('containers', []))

            # Get timestamp from directory name or manifest
            timestamp = self._extract_timestamp(backup_dir.name)

            return {
                'path': str(backup_dir),
                'name': backup_dir.name,
                'timestamp': timestamp,
                'container_count': container_count,
                'containers': containers,
                'source_host': backup_info.get('host', 'Unknown'),
                'size': self._get_directory_size(backup_dir)
            }

        except Exception as e:
            # Not a valid backup
            return None

    def _file_exists(self, path: Path) -> bool:
        """Check if file exists (with sudo if needed)."""
        if self.use_sudo:
            result = subprocess.run(
                ['sudo', 'test', '-f', str(path)],
                capture_output=True
            )
            return result.returncode == 0
        else:
            return path.exists() and path.is_file()

    def _read_file(self, path: Path) -> str:
        """Read file content (with sudo if needed)."""
        if self.use_sudo:
            result = subprocess.run(
                ['sudo', 'cat', str(path)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout
            else:
                raise RuntimeError(f"Failed to read file: {result.stderr}")
        else:
            return path.read_text()

    def _get_directory_size(self, path: Path) -> str:
        """Get human-readable directory size."""
        try:
            # Always use du command (works with or without sudo)
            cmd = ['du', '-sh', str(path)]
            if self.use_sudo:
                cmd = ['sudo'] + cmd

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                size = result.stdout.split()[0]
                return size
        except Exception:
            return "Unknown"

        return "Unknown"

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"

    def _extract_timestamp(self, dirname: str) -> str:
        """Extract timestamp from directory name."""
        # Try to find timestamp pattern: YYYYMMDD_HHMMSS
        import re
        pattern = r'(\d{8}_\d{6})'
        match = re.search(pattern, dirname)

        if match:
            timestamp_str = match.group(1)
            try:
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        return "Unknown"

    def get_default_backup_dirs(self) -> List[str]:
        """
        Get list of common backup directory locations.

        Returns:
            List of potential backup directories
        """
        return [
            "/backups/stacks",
            "/backups/containers",
            "/backups",
            str(Path.home() / "backups"),
            str(Path.cwd() / "backups"),
            "./backups"
        ]

    def find_backups(self, search_dirs: Optional[List[str]] = None) -> List[Dict]:
        """
        Search multiple directories for backups.

        Args:
            search_dirs: List of directories to search (uses defaults if None)

        Returns:
            Combined list of all found backups
        """
        if search_dirs is None:
            search_dirs = self.get_default_backup_dirs()

        all_backups = []
        seen_paths = set()

        for directory in search_dirs:
            dir_path = Path(directory)
            if self._can_read_directory(dir_path):
                backups = self.scan_directory(str(dir_path))
                for backup in backups:
                    # Avoid duplicates
                    if backup['path'] not in seen_paths:
                        all_backups.append(backup)
                        seen_paths.add(backup['path'])

        return all_backups
