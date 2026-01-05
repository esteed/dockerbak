# Dockerbak Project Structure

```
dockerbak/
│
├── dockerbak.py              # Main entry point - run this to start the tool
├── setup.sh                  # Setup script to install dependencies
├── requirements.txt          # Python dependencies
├── README.md                 # Complete documentation and usage guide
├── PROJECT_STRUCTURE.md      # This file
├── .gitignore               # Git ignore patterns
│
└── src/                      # Source code directory
    ├── __init__.py          # Package initialization
    ├── credentials.py       # Secure credential management with encryption
    ├── connection.py        # SSH connection handler
    ├── docker_analyzer.py   # Docker environment analysis
    ├── backup.py           # Backup operations
    ├── restore.py          # Restore instruction generator
    └── cli.py              # CLI interface and user interaction
```

## Module Descriptions

### Main Entry Point

**dockerbak.py**
- Executable script that starts the application
- Initializes CLI and handles program exit

### Core Modules

**src/credentials.py**
- Master password-protected credential storage
- Fernet encryption (AES-128)
- PBKDF2 key derivation with 600,000 iterations
- Secure file permissions

**src/connection.py**
- SSH connection management via paramiko
- Remote command execution
- SFTP file transfers
- Connection pooling

**src/docker_analyzer.py**
- Remote Docker inspection
- Container and stack detection
- Volume and network analysis
- Configuration export

**src/backup.py**
- Container backup operations
- Volume data archival
- Metadata extraction
- Manifest generation with checksums

**src/restore.py**
- Restore instruction generation
- Docker run command reconstruction
- Step-by-step restoration guides
- Troubleshooting tips

**src/cli.py**
- Interactive terminal interface
- Menu system with questionary
- Progress indicators with rich
- User flow orchestration

## Data Storage

### User Home Directory (~/.dockerbak/)
Created on first run to store encrypted credentials:

```
~/.dockerbak/
├── credentials.enc    # Encrypted SSH credentials (600 permissions)
└── salt              # Salt for key derivation
```

### Backup Directory Structure
Created when performing backups:

```
backup_YYYYMMDD_HHMMSS/
├── manifest.json                    # Backup manifest with checksums
├── RESTORE_INSTRUCTIONS.md          # Detailed restoration guide
│
└── container_name/                  # One directory per container
    ├── metadata.json               # Container configuration
    ├── networks.json               # Network settings
    ├── docker-compose.yml          # Compose file (if applicable)
    │
    └── volumes/                     # Volume backups
        ├── volume_name.tar.gz      # Compressed volume data
        └── volume_name.json        # Volume metadata
```

## Dependencies

All Python dependencies are listed in `requirements.txt`:

- **paramiko** - SSH connectivity
- **cryptography** - Credential encryption
- **click** - CLI framework
- **rich** - Terminal formatting
- **questionary** - Interactive prompts
- **pyyaml** - YAML parsing

## Quick Start

1. Install dependencies:
   ```bash
   ./setup.sh
   ```

2. Run the tool:
   ```bash
   ./dockerbak.py
   ```

3. Follow the interactive prompts

## Architecture Flow

```
User Input
    ↓
CLI Interface (cli.py)
    ↓
Credential Manager (credentials.py) → Master Password Unlock
    ↓
SSH Connection (connection.py) → Connect to Remote Host
    ↓
Docker Analyzer (docker_analyzer.py) → Analyze Containers/Stacks
    ↓
Backup Module (backup.py) → Create Backups
    ↓
Restore Generator (restore.py) → Generate Instructions
    ↓
Display Summary & Exit
```

## Security Model

1. **Master Password**: Never stored, only in memory during session
2. **Credential Encryption**: Fernet symmetric encryption
3. **Key Derivation**: PBKDF2 with SHA256, 600k iterations
4. **File Permissions**: 600 on sensitive files
5. **No Plaintext Storage**: All credentials encrypted at rest
