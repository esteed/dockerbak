# Sudo Support for Docker Commands

## Problem
On many Linux systems, Docker requires root privileges or membership in the `docker` group. Users who don't have direct Docker access get permission denied errors when trying to connect to the Docker daemon socket.

## Solution
Dockerbak now supports using `sudo` for all Docker commands. When enabled, all Docker commands are prefixed with `sudo`.

## Changes Made

### 1. DockerAnalyzer (src/docker_analyzer.py)
- Added `use_sudo` parameter to `__init__`
- Modified `_run_docker_command` to prepend `sudo` when enabled
- All Docker inspect, list, and version commands now support sudo

### 2. DockerBackup (src/backup.py)
- Inherits `use_sudo` from analyzer
- Added sudo support to volume backup commands
- Docker run commands for volume archival now use sudo when needed

### 3. CLI Interface (src/cli.py)
- Added `_prompt_sudo()` method to ask user if sudo is needed
- Prompts after connection but before Docker availability check
- Passes `use_sudo` flag to analyzer and backup modules

### 4. Test Script (test_live.py)
- Added sudo prompt before connection test
- Shows "Using sudo for Docker commands" message when enabled

## Usage

### Interactive Prompt
When running Dockerbak, you'll be asked:

```
Docker Configuration
? Use sudo for Docker commands? (y/N)
```

Select `y` if:
- You get "permission denied" errors
- Your user is not in the docker group
- Docker requires root/sudo on your system

Select `n` if:
- Your user is in the docker group
- You have direct Docker access
- You're connecting as root

### Test Script
```bash
./test_live.py
```

When prompted:
```
Use sudo for Docker commands? (y/n) [n]: y
```

## Requirements

For sudo to work:
1. Your SSH user must have sudo privileges on the remote host
2. Sudo should be configured to not require a password (or you'll need to handle prompts)
3. The user must have permissions to run Docker commands via sudo

## Recommended Setup

On the remote Docker host, add your user to the docker group (alternative to sudo):

```bash
# On remote host (as root)
sudo usermod -aG docker your_username

# Log out and log back in for changes to take effect
```

If you prefer to use sudo instead:

```bash
# Configure passwordless sudo for docker (optional)
echo "your_username ALL=(ALL) NOPASSWD: /usr/bin/docker" | sudo tee /etc/sudoers.d/docker-nopasswd
sudo chmod 0440 /etc/sudoers.d/docker-nopasswd
```

## Testing

Run the test script to verify sudo support:

```bash
./test_live.py
```

Enter your connection details and select `y` for sudo when prompted.

## Commands Affected

All Docker commands now support sudo:
- `docker --version`
- `docker ps`
- `docker inspect`
- `docker network ls`
- `docker network inspect`
- `docker run` (for volume backups)
- All other Docker CLI commands

## Troubleshooting

**Issue: "sudo: no tty present and no askpass program specified"**

Solution: Configure passwordless sudo for Docker commands (see Recommended Setup above)

**Issue: Still getting permission denied**

Solutions:
1. Verify your user has sudo privileges: `sudo -l`
2. Try running manually: `ssh user@host "sudo docker ps"`
3. Check Docker daemon is running: `sudo systemctl status docker`

**Issue: Prompted for password on every command**

Solution: Configure passwordless sudo (see above) or add user to docker group instead of using sudo
