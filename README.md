# Dockerbak

A comprehensive Docker backup and restore tool that connects to remote systems, analyzes Docker environments, and creates complete backups with step-by-step restoration instructions.

## Features

- **Secure Credential Management**: Master password-protected encrypted storage for SSH credentials
- **Remote Docker Analysis**: Connect to any Docker host via SSH and analyze containers/stacks
- **Comprehensive Backups**:
  - Container configurations and metadata
  - Volume data (full backup of all mounted volumes)
  - Docker Compose files
  - Network configurations
- **Interactive CLI**: Beautiful terminal interface with menus and progress indicators
- **Automatic Restore Instructions**: Generates detailed markdown guides for restoring containers
- **Stack Support**: Detect and backup entire Docker Compose stacks
- **Flexible**: Backup individual containers or complete stacks

## Installation

### Prerequisites

- Python 3.8 or higher
- SSH access to the remote Docker host
- Docker installed on the remote host

### Setup

1. Clone or download this repository:
```bash
cd dockerbak
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make the script executable:
```bash
chmod +x dockerbak.py
```

## Usage

### Quick Start

Run Dockerbak:
```bash
./dockerbak.py
```

Or with Python:
```bash
python3 dockerbak.py
```

### First Run

On your first run, you'll be prompted for:

1. **Master Password**: This password protects your encrypted credential store. Choose a strong password and remember it - it's never stored anywhere.

2. **SSH Connection Details**:
   - Hostname or IP address
   - SSH username
   - SSH port (default: 22)
   - Authentication method (password or SSH key)
   - Your SSH credentials

3. **Save Credentials**: You can choose to save credentials for future use (recommended)

### Subsequent Runs

After the initial setup:

1. Enter your master password to unlock the credential store
2. Select a saved connection or add a new one
3. Choose what to backup from the interactive menu

## Features in Detail

### Credential Management

Credentials are stored encrypted using:
- **Fernet symmetric encryption** (AES-128)
- **PBKDF2 key derivation** with 600,000 iterations
- **Master password** that's never stored, only used to derive encryption keys
- **Secure file permissions** (600) on credential files

Credential files are stored in `~/.dockerbak/`:
- `credentials.enc` - Encrypted credentials
- `salt` - Salt for key derivation

### Backup Contents

Each backup includes:

1. **metadata.json**: Complete container configuration
   - Image name and version
   - Environment variables
   - Labels and annotations
   - Port mappings
   - Restart policies
   - Resource limits
   - And more...

2. **volumes/**: Compressed archives of volume data
   - Named volumes
   - Bind mounts
   - Volume metadata

3. **networks.json**: Network configuration
   - Network names
   - Network settings
   - IP addresses

4. **docker-compose.yml**: Compose file (if part of a stack)

5. **manifest.json**: Backup manifest with checksums

6. **RESTORE_INSTRUCTIONS.md**: Detailed restoration guide

### Backup Structure

```
backup_20240115_143022/
├── manifest.json
├── RESTORE_INSTRUCTIONS.md
└── my-container/
    ├── metadata.json
    ├── networks.json
    ├── docker-compose.yml
    └── volumes/
        ├── data_volume.tar.gz
        ├── data_volume.json
        ├── config_volume.tar.gz
        └── config_volume.json
```

## Menu Options

### Main Menu

- **Backup individual container**: Select one or more containers to backup
- **Backup Docker Compose stack**: Backup an entire stack with all its containers
- **List all containers**: View all containers on the remote host
- **List all stacks**: View all Docker Compose stacks
- **Exit**: Disconnect and exit

### Backup Process

1. Select containers/stack to backup
2. Choose backup directory (default: `/backups` - automatically uses sudo if needed)
3. Watch the progress as backup proceeds
4. Review backup summary with location of restore instructions

## Restoring from Backup

After creating a backup, detailed restore instructions are automatically generated in `RESTORE_INSTRUCTIONS.md` within the backup directory.

The restore instructions include:

1. **Prerequisites**: What you need before restoring
2. **Network Creation**: Commands to recreate Docker networks
3. **Volume Restoration**: Steps to restore volume data
4. **Container Creation**: Complete `docker run` commands or `docker-compose` deployment
5. **Verification**: How to verify the restoration
6. **Troubleshooting**: Common issues and solutions

### Example Restore Flow

```bash
# 1. Navigate to backup directory
cd backup_20240115_143022

# 2. Read the instructions
cat RESTORE_INSTRUCTIONS.md

# 3. Follow the step-by-step guide to restore
```

## Security Best Practices

1. **Master Password**: Use a strong, unique master password
2. **SSH Keys**: Prefer SSH key authentication over passwords
3. **Backup Security**: Store backups in secure locations with appropriate permissions
4. **Credential Rotation**: Regularly update stored credentials
5. **Access Control**: Limit who has access to the master password and backups

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to remote host

**Solutions**:
- Verify hostname/IP is correct
- Check SSH port is accessible (firewall rules)
- Confirm SSH credentials are correct
- Test SSH connection manually: `ssh user@host`

### Docker Not Found

**Problem**: Docker not available on remote host

**Solutions**:
- Verify Docker is installed: `ssh user@host "docker --version"`
- Check Docker service is running: `ssh user@host "systemctl status docker"`
- Ensure user has Docker permissions: `ssh user@host "docker ps"`

### Volume Backup Failures

**Problem**: Volume backup fails or is incomplete

**Solutions**:
- Ensure sufficient disk space on remote host (`/tmp`)
- Check volume permissions
- For large volumes, increase timeout in connection settings
- Verify Docker can access the volume

### Invalid Master Password

**Problem**: Cannot unlock credential store

**Solutions**:
- Ensure you're using the correct master password
- If password is forgotten, delete `~/.dockerbak/` and start fresh (you'll lose saved credentials)

## Advanced Usage

### Custom Backup Location

When prompted for backup directory, you can specify any path:
```
Backup directory: /path/to/custom/backups
```

### Selective Container Backup

Use the checkbox menu to select multiple containers:
- Use arrow keys to navigate
- Press Space to select/deselect
- Press Enter to confirm

### Managing Saved Connections

To remove saved connections, delete the specific host from:
```bash
rm ~/.dockerbak/credentials.enc
rm ~/.dockerbak/salt
```

Then recreate with new credentials on next run.

## System Requirements

### Local Machine (where Dockerbak runs)

- Python 3.8+
- 100MB free disk space (plus space for backups)
- Network connectivity to Docker host

### Remote Docker Host

- SSH server running
- Docker installed and running
- Sufficient disk space in `/tmp` for temporary files
- User with Docker permissions

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is provided as-is for personal and commercial use.

## Author

Created with Claude Code

## Version

1.0.0

## Support

For issues, questions, or suggestions, please create an issue in the repository.
