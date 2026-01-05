# Dockerbak Quick Start Guide

## Installation (One-Time Setup)

```bash
cd dockerbak
./setup.sh
```

## First Run

```bash
./dockerbak.py
```

You'll be prompted for:

1. **Master Password** (create a strong one - you'll need it every time)
2. **Remote Host Details:**
   - Hostname/IP: `your-docker-host.com`
   - Username: `root` or your SSH user
   - Port: `22` (default)
   - Auth: Choose Password or SSH Key
   - Credentials: Enter your password or key path

3. **Save Credentials?** → Select `Yes` (recommended)

## Main Menu Options

```
1. Backup individual container  → Back up one or more containers
2. Backup Docker Compose stack   → Back up entire stack
3. List all containers           → View all containers on remote host
4. List all stacks              → View all Docker Compose stacks
5. Exit                         → Disconnect and quit
```

## Backup Workflow

### Individual Container
1. Select "Backup individual container"
2. Check containers to backup (Space to select, Enter to confirm)
3. Enter backup directory path (default: `/backups` - sudo auto-enabled if needed)
4. Wait for backup to complete
5. Review summary with restore instructions location

### Docker Compose Stack
1. Select "Backup Docker Compose stack"
2. Choose stack from list
3. Enter backup directory path
4. Wait for backup to complete
5. Review summary

## Restore from Backup

1. Navigate to backup directory:
   ```bash
   cd backup_20260101_165700
   ```

2. Read the instructions:
   ```bash
   cat RESTORE_INSTRUCTIONS.md
   ```

3. Follow the step-by-step commands in the instructions

## What Gets Backed Up

✓ Container configuration (env vars, ports, labels, etc.)
✓ Volume data (complete compressed archives)
✓ Network settings
✓ Docker Compose files (if part of stack)
✓ Restore instructions
✓ Backup manifest with checksums

## Backup Location

Default backup structure:
```
backup_YYYYMMDD_HHMMSS/
├── manifest.json
├── RESTORE_INSTRUCTIONS.md
└── container_name/
    ├── metadata.json
    ├── networks.json
    ├── docker-compose.yml (if applicable)
    └── volumes/
        └── *.tar.gz
```

## Tips

- **Security**: Your master password is never stored anywhere
- **Credentials**: Stored encrypted at `~/.dockerbak/credentials.enc`
- **Multiple Hosts**: You can save credentials for multiple Docker hosts
- **Backup Size**: Volume backups can be large - ensure sufficient disk space
- **Network Speed**: Backup time depends on volume size and network speed

## Common Commands

```bash
# Run Dockerbak
./dockerbak.py

# Run tests
python3 test_functionality.py

# Validate imports
python3 test_imports.py

# Check backup size
du -sh backup_*

# View restore instructions
cat backup_*/RESTORE_INSTRUCTIONS.md
```

## Troubleshooting

**Can't connect to remote host?**
- Verify SSH access: `ssh user@host`
- Check firewall rules
- Confirm Docker is running on remote host

**Wrong master password?**
- No recovery possible - delete `~/.dockerbak/` and start fresh
- You'll need to re-enter all saved credentials

**Backup failed?**
- Check disk space on both local and remote systems
- Verify Docker permissions on remote host
- Check logs for specific error messages

## Support

- Documentation: `README.md`
- Architecture: `PROJECT_STRUCTURE.md`
- Test Results: `TEST_RESULTS.md`

---

**Quick Example Session:**

```bash
$ ./dockerbak.py

🐳 Dockerbak - Docker Backup & Restore Tool

Enter master password: ************
✓ Credential store unlocked.

Select a host:
❯ docker.example.com
  Add new connection

✓ Connected to docker.example.com
✓ Docker version: 24.0.7

Main Menu
What would you like to do?
❯ Backup individual container
  Backup Docker Compose stack
  List all containers
  List all stacks
  Exit

Select containers to backup:
❯ ◉ web-app (nginx:latest)
  ◯ database (postgres:15)
  ◉ redis (redis:alpine)

Backup directory: ./backups

Backing up to: /home/user/backups/backup_20260101_165700

✓ Backup completed successfully!

Location: /home/user/backups/backup_20260101_165700
Restore instructions: /home/user/backups/backup_20260101_165700/RESTORE_INSTRUCTIONS.md
```
