#!/usr/bin/env python3
"""
Test script to validate all modules can be imported correctly.
"""

import sys

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        print("  ✓ Importing credentials module...", end=" ")
        from src.credentials import CredentialManager
        print("OK")

        print("  ✓ Importing connection module...", end=" ")
        from src.connection import SSHConnection
        print("OK")

        print("  ✓ Importing docker_analyzer module...", end=" ")
        from src.docker_analyzer import DockerAnalyzer
        print("OK")

        print("  ✓ Importing backup module...", end=" ")
        from src.backup import DockerBackup
        print("OK")

        print("  ✓ Importing restore module...", end=" ")
        from src.restore import RestoreInstructionsGenerator
        print("OK")

        print("  ✓ Importing cli module...", end=" ")
        from src.cli import DockerBakCLI
        print("OK")

        print("\n✓ All imports successful!")

        # Test credential manager instantiation
        print("\nTesting CredentialManager instantiation...", end=" ")
        cm = CredentialManager()
        print("OK")

        print(f"  - Dockerbak directory: {cm.DOCKERBAK_DIR}")
        print(f"  - Credentials file: {cm.CREDENTIALS_FILE}")
        print(f"  - Salt file: {cm.SALT_FILE}")

        # Test SSH connection instantiation
        print("\nTesting SSHConnection instantiation...", end=" ")
        conn = SSHConnection()
        print("OK")

        print("\n" + "="*50)
        print("All validation tests passed!")
        print("="*50)
        print("\nDockerBak is ready to use!")
        print("Run: ./dockerbak.py")

        return 0

    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(test_imports())
