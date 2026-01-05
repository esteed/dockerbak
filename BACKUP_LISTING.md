# Backup Listing Feature

## Overview
Dockerbak can now automatically scan and list all available backups, making it easy to select which backup to restore without manually browsing directories.

## Features

### Automatic Backup Discovery
- Scans common backup locations automatically
- Detects and handles sudo requirements for protected directories
- Validates backups (checks for manifest.json)
- Extracts metadata from each backup

### Smart Scanning Locations
Default locations checked (in order):
1. `/backups` - System-wide backups
2. `~/backups` - User home directory
3. `./backups` - Current directory
4. Any custom location via manual browse

### Sudo Detection for Scanning
If backups are stored in protected directories (like `/backups`), the scanner:
- Detects permission requirements automatically
- Prompts to use sudo for scanning
- Uses sudo commands to read manifests and calculate sizes

## How to Use

### Step 1: Start Restore
```
Main Menu
? What would you like to do?
❯ Restore from backup
```

### Step 2: Choose Selection Method
```
? How would you like to select a backup?
❯ List available backups              ← Auto-scan and display
  Browse to backup directory manually  ← Manual path entry
```

### Step 3: View Available Backups

**If backups found:**
```
Scanning for backups...

Found 3 backup(s):

┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┓
┃ #  ┃ Backup Name            ┃ Date/Time          ┃ Containers     ┃ Source Host ┃ Size  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━┩
│ 1  │ nginx_20260101_153045  │ 2026-01-01 15:30:45│ 1: nginx       │ 192.168.1.35│ 245MB │
│ 2  │ postgres_20260101_140000│ 2026-01-01 14:00:00│ 1: postgres    │ 192.168.1.35│ 1.2GB │
│ 3  │ 3_containers_20260101  │ 2026-01-01 12:00:00│ 3: webapp      │ 192.168.1.40│ 512MB │
└────┴────────────────────────┴────────────────────┴────────────────┴─────────────┴───────┘

? Select a backup to restore:
❯ 1. nginx_20260101_153045 (2026-01-01 15:30:45)
  2. postgres_20260101_140000 (2026-01-01 14:00:00)
  3. 3_containers_20260101 (2026-01-01 12:00:00)
  Cancel
```

**If sudo needed:**
```
Scanning for backups...
⚠ '/backups' requires elevated privileges
? Use sudo to scan backup directories? (Y/n) Y

Found 2 backup(s):
...
```

**If no backups found:**
```
Scanning for backups...

No backups found in common locations.
Common locations checked:
  - /backups
  - /home/user/backups
  - ./backups

Tip: Use 'Browse to backup directory manually' to specify a custom location.
```

### Step 4: Select and Restore
Choose a backup from the list, then proceed with normal restore flow.

## What Information Is Shown

For each backup, the table displays:

| Column | Description |
|--------|-------------|
| **#** | Selection number |
| **Backup Name** | Directory name (includes container name and timestamp) |
| **Date/Time** | When backup was created |
| **Containers** | Number of containers and first container name |
| **Source Host** | Original Docker host where backup was created |
| **Size** | Total backup size (including volumes) |

## Technical Details

### Backup Validation

A directory is considered a valid backup if it:
1. Contains a `manifest.json` file
2. Manifest is valid JSON
3. Contains backup_info metadata

### Metadata Extraction

For each backup, the scanner reads:
- Container names and count
- Stack information (if applicable)
- Source hostname
- Timestamp from directory name
- Total size (calculated or via du -sh)

### Sudo Handling

The BackupScanner class handles sudo automatically:

```python
scanner = BackupScanner(use_sudo=True)
```

When sudo is enabled:
- Uses `sudo find` to list directories
- Uses `sudo cat` to read manifest files
- Uses `sudo du -sh` to calculate sizes
- Uses `sudo test` to check permissions

### Performance

- **Fast scanning**: Only reads manifest.json from each backup
- **Sorted results**: Newest backups shown first
- **Duplicate detection**: Same backup in multiple locations shown once
- **Lazy loading**: Sizes calculated on-demand

## Use Cases

### Quick Restore
```
1. Select "Restore from backup"
2. Select "List available backups"
3. Choose from table
4. Restore!
```

### Protected Backups
```
Backups in /backups/ (requires root)
↓
Scanner detects sudo requirement
↓
Prompts for sudo access
↓
Lists all backups successfully
```

### Multiple Backup Locations
```
Backups in:
- /backups/nginx_backup
- ~/backups/postgres_backup
- ./backups/redis_backup

All shown in one combined list!
```

## Advantages Over Manual Browsing

| Manual Browse | Auto List |
|--------------|-----------|
| Navigate filesystem | See all at once |
| Remember paths | Automatic discovery |
| Type full path | Select with arrows |
| No metadata shown | Full info displayed |
| No sorting | Newest first |

## Example Session

```bash
./dockerbak.py

Main Menu
? What would you like to do? Restore from backup

? How would you like to select a backup?
  List available backups

Scanning for backups...
Found 5 backup(s):

┏━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┓
┃ #  ┃ Backup Name         ┃ Date/Time          ┃ Containers ┃ Source Host ┃ Size ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━┩
│ 1  │ nginx_20260101_1600 │ 2026-01-01 16:00:00│ 1: nginx   │ prod-server │ 128MB│
│ 2  │ nginx_20260101_1200 │ 2026-01-01 12:00:00│ 1: nginx   │ prod-server │ 125MB│
│ 3  │ postgres_20260101   │ 2026-01-01 10:00:00│ 1: postgres│ db-server   │ 2.1GB│
│ 4  │ stack_app_20260101  │ 2026-01-01 08:00:00│ 5: Stack   │ app-cluster │ 890MB│
│ 5  │ redis_20251231      │ 2025-12-31 18:00:00│ 1: redis   │ cache-srv   │ 64MB │
└────┴─────────────────────┴────────────────────┴────────────┴─────────────┴──────┘

? Select a backup to restore:
❯ 1. nginx_20260101_1600 (2026-01-01 16:00:00)

Found 1 container(s) in backup:
...

[Restore proceeds normally]
```

## Configuration

### Custom Search Paths

To add custom backup locations, modify `BackupScanner.get_default_backup_dirs()`:

```python
def get_default_backup_dirs(self):
    return [
        "/backups",
        "/mnt/nas/docker-backups",  # Network storage
        "/opt/backups",             # Custom location
        str(Path.home() / "backups")
    ]
```

### Disable Sudo Prompting

Pass `use_sudo=False` to always scan without sudo:

```python
scanner = BackupScanner(use_sudo=False)
```

## Troubleshooting

### No Backups Found

**Cause**: Backups in non-standard location

**Solution**:
1. Use "Browse to backup directory manually"
2. Or add location to default search paths

### Permission Denied

**Cause**: Backups in protected directory

**Solution**: Answer "Yes" to sudo prompt when scanning

### Invalid Backup Detected

**Cause**: Directory missing manifest.json or corrupt

**Solution**: Backup is skipped automatically, other valid backups still shown

### Slow Scanning

**Cause**: Large number of directories or slow filesystem

**Solution**:
- Scanner only reads manifests (fast)
- Size calculation may be slow on network drives
- Consider organizing backups in dedicated directory

## Benefits

✓ **Time Saving** - No manual path navigation
✓ **Visibility** - See all backups at once
✓ **Context** - Know what's in each backup before selecting
✓ **Safety** - Validate backups before attempting restore
✓ **Organization** - Sorted by date, newest first
✓ **Flexibility** - Both auto-list and manual browse available
✓ **Sudo Aware** - Handles protected directories automatically
