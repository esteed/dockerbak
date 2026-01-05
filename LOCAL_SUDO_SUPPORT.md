# Local Sudo Support for Backups

## New Features

### 1. Local Sudo for Backup Operations
Dockerbak now detects when the backup directory requires elevated privileges and prompts to use sudo for local file operations.

**When is this needed?**
- Writing to system directories like `/backups`
- Creating directories in locations owned by root
- Any directory where your user lacks write permissions

### 2. Container Name in Backup Directory
Backup directories are now named with the container name and timestamp for easy identification.

**Format:**
- Single container: `container-name_YYYYMMDD_HHMMSS`
- Multiple containers: `N_containers_YYYYMMDD_HHMMSS`
- Docker stack: `stack_project-name_YYYYMMDD_HHMMSS`

**Examples:**
- `nginx_20260101_143022` - Single nginx container backup
- `3_containers_20260101_143530` - Three containers backed up together
- `stack_myapp_20260101_144000` - Docker Compose stack backup

## How It Works

### Automatic Detection
When you select a backup directory, Dockerbak checks if it's writable:

```
Backup directory: /backups

⚠ Warning: '/backups' requires elevated privileges
? Use sudo for backup file operations? (Y/n)
```

### If You Select Yes
- Backup directories created with `sudo mkdir`
- Ownership automatically changed to your user
- All subsequent file operations work normally

### If You Select No
- Standard mkdir without sudo
- You may encounter "Permission denied" errors
- Use if you want to change the backup location instead

## Usage Example

### Scenario 1: System Directory Backup
```bash
./dockerbak.py

# ... connection setup ...

Select "Backup individual container"
Select container: nginx

Backup directory: /backups

⚠ Warning: '/backups' requires elevated privileges
? Use sudo for backup file operations? Yes

Will use sudo for backup directory creation

Backing up to: /backups/nginx_20260101_143022

[Backup proceeds successfully]
```

### Scenario 2: User Directory Backup (No Sudo Needed)
```bash
./dockerbak.py

# ... connection setup ...

Backup directory: ./backups

[No sudo prompt - directory is writable]

Backing up to: ./backups/webapp_20260101_143530
```

## Technical Details

### New Components

**LocalSudoHelper** (`src/local_sudo.py`)
- Checks directory permissions
- Creates directories with sudo when needed
- Automatically sets ownership to current user
- Handles permission errors gracefully

**Updated Methods:**
- `create_backup_directory()` - Now accepts `container_name` parameter
- `_check_local_sudo()` - Prompts for sudo when needed
- `_perform_backup()` - Passes container name to directory creation
- `_perform_stack_backup()` - Passes stack name to directory creation

### Security Considerations

1. **Sudo Commands Used:**
   - `sudo mkdir -p <path>` - Create directory
   - `sudo chmod 755 <path>` - Set permissions
   - `sudo chown user:group <path>` - Change ownership

2. **Why It's Safe:**
   - Only creates directories, doesn't modify existing files
   - Ownership immediately transferred to your user
   - No write access to system files
   - Limited to specific backup directory operations

3. **Recommendations:**
   - Use user-owned directories when possible (~/backups)
   - Only use sudo for system directories when necessary
   - Verify backup directory path before confirming sudo

## Troubleshooting

### Issue: "sudo: no tty present"
**Solution:** Run dockerbak from an interactive terminal, not as a background process

### Issue: Still getting permission denied
**Solutions:**
1. Verify your user has sudo privileges: `sudo -l`
2. Try a user-owned directory instead: `~/backups` or `/tmp/backups`
3. Pre-create the directory with correct permissions:
   ```bash
   sudo mkdir -p /backups
   sudo chown $USER:$USER /backups
   ```

### Issue: Prompted for password multiple times
**Solution:** Configure passwordless sudo (optional):
```bash
echo "$USER ALL=(ALL) NOPASSWD: /bin/mkdir, /bin/chmod, /bin/chown" | \
  sudo tee /etc/sudoers.d/dockerbak-nopass
sudo chmod 0440 /etc/sudoers.d/dockerbak-nopass
```

## Benefits

✓ **No manual directory creation** - Dockerbak handles it automatically
✓ **Clear backup organization** - Easy to find specific container backups
✓ **Flexible permissions** - Works with both user and system directories
✓ **Secure** - Minimal sudo usage, proper ownership handling
✓ **Informative naming** - Know what was backed up and when at a glance

## Examples of Backup Directory Names

```
/backups/
├── nginx_20260101_143022/              # Single nginx container
├── postgres_20260101_150000/           # Single postgres container
├── 5_containers_20260101_160000/       # Multiple containers
├── stack_wordpress_20260101_170000/    # WordPress stack
└── stack_monitoring_20260101_180000/   # Monitoring stack
```

Each directory contains:
- Container metadata
- Volume data
- Network configs
- Docker Compose files (if applicable)
- Restore instructions
- Backup manifest
