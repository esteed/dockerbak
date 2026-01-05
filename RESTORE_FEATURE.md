# Restore Feature Documentation

## Overview
Dockerbak now includes comprehensive restore functionality, allowing you to restore backed-up containers to the same host or a completely different target host.

## Features

### 1. Interactive Restore Menu
- Browse and select backup directories
- View all containers in a backup
- Select specific containers or restore all
- Choose target host (current or different)

### 2. Multi-Host Restore Support
- Restore to the same host where backup was created
- Restore to a completely different Docker host
- Automatic credential handling for target hosts
- Independent sudo configuration for target

### 3. Complete Restoration
- **Docker images**: Automatically pulls required images
- **Networks**: Recreates custom Docker networks
- **Volumes**: Restores all volume data with full contents
- **Containers**: Recreates containers with original configuration

### 4. Enter Key Confirmation
All menu selections now explicitly require pressing Enter to confirm, preventing accidental selections.

## How to Use

### Step 1: Access Restore Menu

```
Main Menu
? What would you like to do?
  Backup individual container
  Backup Docker Compose stack
❯ Restore from backup          ← Select this
  List all containers
  List all stacks
  Exit
```

Press ↓ arrow to navigate, Enter to select.

### Step 2: Select Backup Directory

```
? Path to backup directory: /backups/nginx_20260101_143022
```

Browse to your backup folder and press Enter.

### Step 3: Review Containers

```
Found 1 container(s) in backup:

┏━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ # ┃ Container Name  ┃ Image         ┃
┡━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ 1 │ nginx           │ nginx:latest  │
└───┴─────────────────┴───────────────┘
```

### Step 4: Select Containers

For single container:
```
Automatically selected
```

For multiple containers:
```
? Restore all containers? (Y/n)
```

Or select specific ones:
```
? Select containers to restore:
 ◯ nginx (nginx:latest)
❯◉ postgres (postgres:15)
 ◯ redis (redis:alpine)
```

Use Space to select, Enter to confirm.

### Step 5: Choose Target Host

**Option A: Restore to Current Host**
```
? Restore to current host (192.168.1.35)? (Y/n) Y
```

**Option B: Restore to Different Host**
```
? Restore to current host (192.168.1.35)? (Y/n) n

Connect to Target Host
? Target hostname or IP: 192.168.1.50
? Username: root
? Password: ********
? Use sudo for Docker commands on target? (y/N)

✓ Connected to 192.168.1.50
```

### Step 6: Restoration Process

```
Restoring 1 container(s)...

━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:45

✓ Restore completed!

Restored 1 container(s)
Target host: 192.168.1.50
```

## Restoration Steps (Automated)

For each container, Dockerbak automatically:

1. **Pulls Docker Image**
   - Downloads the container image to target host
   - Uses the same version as in backup

2. **Restores Networks**
   - Creates custom Docker networks
   - Skips default networks (bridge, host, none)
   - Configures network settings

3. **Restores Volumes**
   - Creates new Docker volumes on target
   - Uploads volume archives via SFTP
   - Extracts data into volumes
   - Names volumes with `_restored` suffix

4. **Creates Container**
   - Recreates container with original:
     - Environment variables
     - Port mappings
     - Labels
     - Restart policies
     - Network connections
     - Volume mounts (using restored volumes)
     - Working directory
     - User configuration

## Volume Naming

Restored volumes are named: `<original_path>_restored`

Example:
- Original: Container mounted `/var/lib/mysql`
- Restored volume: `var_lib_mysql_restored`

This prevents conflicts with existing volumes and clearly identifies restored data.

## Use Cases

### Migration Between Hosts
```
Backup from production server → Restore to staging server
```

### Disaster Recovery
```
Backup from failed server → Restore to replacement server
```

### Development Cloning
```
Backup from production → Restore to local development
```

### Container Replication
```
Backup from server A → Restore to servers B, C, D
```

## Important Notes

### Before Restoring

1. **Check Target Docker Version**
   - Ensure Docker is installed on target
   - Version compatibility with backup images

2. **Verify Network Connectivity**
   - SSH access to target host
   - Sufficient bandwidth for volume transfers
   - Firewall rules allow Docker ports

3. **Ensure Sufficient Space**
   - Disk space for Docker images
   - Volume data storage
   - Temporary space for extraction

### During Restore

- **Container Names**: If a container with the same name exists, restore will fail
- **Port Conflicts**: Ensure ports aren't already in use
- **Image Availability**: Images must be pullable from registries
- **Large Volumes**: May take time depending on size and network speed

### After Restore

1. **Verify Containers**
   ```bash
   docker ps
   docker logs <container_name>
   ```

2. **Check Volume Data**
   ```bash
   docker volume ls
   docker run --rm -v <volume_name>:/data alpine ls /data
   ```

3. **Test Connectivity**
   - Verify port access
   - Test application functionality
   - Check inter-container communication

## Troubleshooting

### Issue: Container Name Conflict
```
Error: Conflict. The container name "/nginx" is already in use
```

**Solution:**
- Stop/remove existing container, or
- Edit metadata.json to change container name

### Issue: Port Already in Use
```
Error: bind: address already in use
```

**Solution:**
- Stop service using the port
- Modify port mappings in metadata.json

### Issue: Image Pull Failed
```
Error: image not found
```

**Solution:**
- Check internet connectivity
- Verify image exists in registry
- Pull image manually first

### Issue: Volume Restore Permission Denied
```
Error: permission denied while trying to connect to Docker daemon
```

**Solution:**
- Answer 'Y' to "Use sudo for Docker commands on target?"
- Or add user to docker group on target

### Issue: Network Already Exists
```
Warning: network already exists
```

**Solution:**
- This is informational, restore will continue
- Network will be reused if compatible

## Advanced Options

### Partial Restore
You can restore only specific containers from a multi-container backup.

### Cross-Platform Restore
Restore supports moving containers between:
- Different Linux distributions
- x86 → x86 (same architecture required for volumes)
- Docker versions (with compatibility)

### Restore Without Volumes
Edit the restore process to skip volume restoration if you only need the container configuration.

## Security Considerations

1. **SSH Credentials**
   - Target host credentials can be saved or entered once
   - Encrypted with master password

2. **Volume Data**
   - Transferred via SFTP (encrypted)
   - Temporary files cleaned up after extraction

3. **Sudo Usage**
   - Only requested when needed
   - Limited to Docker commands

## Performance

### Factors Affecting Restore Time

- **Image Size**: Larger images take longer to pull
- **Volume Data**: More data = longer transfer time
- **Network Speed**: SSH/SFTP transfer rate
- **Target Host**: Disk I/O performance

### Estimated Times

| Component | Small | Medium | Large |
|-----------|-------|--------|-------|
| Image Pull | 10s | 1m | 5m |
| Volume Transfer | 30s | 5m | 30m |
| Container Create | 5s | 10s | 20s |

## Examples

### Example 1: Simple Restore
```
1. Run: ./dockerbak.py
2. Select: Restore from backup
3. Path: ./backups/nginx_20260101_143022
4. Restore all: Yes
5. Current host: Yes
6. Done!
```

### Example 2: Cross-Host Migration
```
1. Run: ./dockerbak.py (connected to source host)
2. Select: Restore from backup
3. Path: ./backups/webapp_20260101_150000
4. Select containers: All 3 containers
5. Current host: No
6. Target: 192.168.1.60
7. Credentials: Enter or use saved
8. Sudo on target: Yes
9. Restore begins
10. Verify on target host
```

### Example 3: Selective Restore
```
1. Run: ./dockerbak.py
2. Select: Restore from backup
3. Path: ./backups/5_containers_20260101_160000
4. Restore all: No
5. Select: Only database container
6. Current host: Yes
7. Database restored, others skipped
```

## Comparison: Manual vs Automated

### Manual Restoration (Old Way)
1. Read RESTORE_INSTRUCTIONS.md
2. Manually create networks
3. Manually create volumes
4. Manually extract volume data
5. Copy/paste docker run commands
6. Debug issues
7. **Time: 15-30 minutes**

### Automated Restoration (Dockerbak)
1. Select backup
2. Choose target
3. Confirm
4. **Time: 2-5 minutes**

## Future Enhancements

Potential features for future versions:
- Restore with configuration modifications
- Scheduled/automated restores
- Restore verification and testing
- Rollback capability
- Multi-target restore (restore to multiple hosts at once)
