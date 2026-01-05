#!/usr/bin/env python3
"""
Functional tests for Dockerbak components.
"""

import sys
import tempfile
import shutil
from pathlib import Path

def test_credential_manager():
    """Test credential manager encryption/decryption."""
    print("\n" + "="*50)
    print("Testing Credential Manager")
    print("="*50)

    from src.credentials import CredentialManager

    # Create temporary directory for test
    test_dir = Path(tempfile.mkdtemp())

    try:
        # Override the default directory for testing
        CredentialManager.DOCKERBAK_DIR = test_dir
        CredentialManager.CREDENTIALS_FILE = test_dir / "credentials.enc"
        CredentialManager.SALT_FILE = test_dir / "salt"

        cm = CredentialManager()

        # Test 1: Unlock with new password
        print("\n1. Testing unlock with new master password...", end=" ")
        result = cm.unlock("test_password_123")
        assert result == True, "Unlock should succeed with new password"
        print("✓ PASS")

        # Test 2: Save credentials
        print("2. Testing save credentials...", end=" ")
        cm.save_credentials(
            host="test.example.com",
            username="testuser",
            password="testpass",
            port=22
        )
        print("✓ PASS")

        # Test 3: Load credentials
        print("3. Testing load credentials...", end=" ")
        creds = cm.load_credentials("test.example.com")
        assert creds is not None, "Credentials should be loaded"
        assert creds['username'] == "testuser", "Username should match"
        assert creds['password'] == "testpass", "Password should match"
        assert creds['port'] == 22, "Port should match"
        print("✓ PASS")

        # Test 4: List hosts
        print("4. Testing list hosts...", end=" ")
        hosts = cm.list_hosts()
        assert "test.example.com" in hosts, "Host should be in list"
        print("✓ PASS")

        # Test 5: Delete credentials
        print("5. Testing delete credentials...", end=" ")
        result = cm.delete_credentials("test.example.com")
        assert result == True, "Delete should succeed"
        hosts = cm.list_hosts()
        assert "test.example.com" not in hosts, "Host should be removed"
        print("✓ PASS")

        # Test 6: Wrong password
        print("6. Testing wrong password rejection...", end=" ")
        cm2 = CredentialManager()
        cm2.unlock("test_password_123")
        cm2.save_credentials("host2", "user2", "pass2", port=22)

        cm3 = CredentialManager()
        result = cm3.unlock("wrong_password")
        assert result == False, "Wrong password should fail"
        print("✓ PASS")

        print("\n✓ All Credential Manager tests passed!")
        return True

    except AssertionError as e:
        print(f"\n✗ FAIL: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)


def test_restore_generator():
    """Test restore instruction generator."""
    print("\n" + "="*50)
    print("Testing Restore Instructions Generator")
    print("="*50)

    from src.restore import RestoreInstructionsGenerator
    import json

    # Create test backup structure
    test_dir = Path(tempfile.mkdtemp())

    try:
        # Create mock container backup
        container_dir = test_dir / "test_container"
        container_dir.mkdir()

        # Create metadata
        metadata = {
            "name": "test_container",
            "image": "nginx:latest",
            "env": ["ENV_VAR=value"],
            "port_bindings": {"80/tcp": [{"HostPort": "8080"}]},
            "mounts": [],
            "restart_policy": {"Name": "always"}
        }
        with open(container_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f)

        # Create networks
        with open(container_dir / "networks.json", 'w') as f:
            json.dump({"bridge": {}}, f)

        # Test generation
        print("\n1. Testing instruction generation...", end=" ")
        generator = RestoreInstructionsGenerator(test_dir)
        instructions_file = generator.generate_instructions()
        assert instructions_file.exists(), "Instructions file should be created"
        print("✓ PASS")

        # Test content
        print("2. Testing instruction content...", end=" ")
        content = instructions_file.read_text()
        assert "Docker Container Restore Instructions" in content, "Should have title"
        assert "test_container" in content, "Should mention container name"
        assert "Prerequisites" in content, "Should have prerequisites"
        assert "Verification" in content, "Should have verification section"
        assert "Troubleshooting" in content, "Should have troubleshooting"
        print("✓ PASS")

        print("\n✓ All Restore Generator tests passed!")
        return True

    except AssertionError as e:
        print(f"\n✗ FAIL: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)


def test_ssh_connection():
    """Test SSH connection instantiation."""
    print("\n" + "="*50)
    print("Testing SSH Connection")
    print("="*50)

    from src.connection import SSHConnection

    try:
        print("\n1. Testing instantiation...", end=" ")
        conn = SSHConnection()
        assert conn.client is None, "Client should be None initially"
        assert conn.sftp is None, "SFTP should be None initially"
        print("✓ PASS")

        print("2. Testing is_connected...", end=" ")
        assert conn.is_connected() == False, "Should not be connected"
        print("✓ PASS")

        print("\n✓ All SSH Connection tests passed!")
        return True

    except AssertionError as e:
        print(f"\n✗ FAIL: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Dockerbak Functionality Tests")
    print("="*60)

    results = []

    # Run tests
    results.append(("Credential Manager", test_credential_manager()))
    results.append(("Restore Generator", test_restore_generator()))
    results.append(("SSH Connection", test_ssh_connection()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:.<40} {status}")

    print("\n" + "="*60)
    print(f"Results: {passed}/{total} test suites passed")
    print("="*60)

    if passed == total:
        print("\n✓ All tests passed! Dockerbak is working correctly.")
        return 0
    else:
        print(f"\n✗ {total - passed} test suite(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
