#!/usr/bin/env python3
"""
Test script for KeePassXC integration debugging.
This script helps diagnose KeePassXC configuration and connectivity issues.
"""

import sys
from pathlib import Path
from creature_config import config as creature_config
from keepassxc_manager import keepass_manager, KeePassXCError

def test_keepassxc_setup():
    """Test KeePassXC configuration and basic functionality."""
    print("=== KeePassXC Integration Test ===\n")
    
    # Test 1: Configuration
    print("1. Configuration Test:")
    print(f"   KeePassXC enabled: {creature_config.keepassxc.enabled}")
    print(f"   Database path: {creature_config.keepassxc.database_path}")
    print(f"   Key file: {creature_config.keepassxc.key_file}")
    print(f"   Show context menu: {creature_config.keepassxc.show_context_menu}")
    print(f"   Clip timeout: {creature_config.keepassxc.clip_timeout}")
    
    # Test 2: KeePassXC CLI availability
    print("\n2. KeePassXC CLI Test:")
    print(f"   Manager enabled: {keepass_manager.enabled}")
    if keepass_manager._is_cli_available():
        print("   ✅ keepassxc-cli is available")
    else:
        print("   ❌ keepassxc-cli is NOT available")
        print("   Install KeePassXC: sudo apt install keepassxc")
        return False
    
    # Test 3: Database file existence
    print("\n3. Database File Test:")
    expanded_path = keepass_manager._expand_path(creature_config.keepassxc.database_path)
    print(f"   Expanded database path: {expanded_path}")
    if Path(expanded_path).exists():
        print("   ✅ Database file exists")
    else:
        print("   ❌ Database file does NOT exist")
        print(f"   Please check the path: {expanded_path}")
        return False
    
    # Test 4: Key file (if specified)
    if creature_config.keepassxc.key_file:
        print("\n4. Key File Test:")
        key_file_path = keepass_manager._expand_path(creature_config.keepassxc.key_file)
        print(f"   Key file path: {key_file_path}")
        if Path(key_file_path).exists():
            print("   ✅ Key file exists")
        else:
            print("   ❌ Key file does NOT exist")
            return False
    
    # Test 5: Manual password test
    print("\n5. Manual Password Test:")
    if not creature_config.keepassxc.enabled:
        print("   ⚠️  KeePassXC is disabled in configuration")
        print("   Enable it by setting 'enabled = True' in [keepassxc] section")
        return False
    
    print("   Enter your master password to test database access:")
    try:
        import getpass
        master_password = getpass.getpass("   Master password: ")
        
        print(f"   Testing password (length: {len(master_password)} characters)...")
        if keepass_manager.test_database_access(master_password):
            print("   ✅ Password accepted! Database access successful")
            
            # Test 6: List entries
            print("\n6. Database Content Test:")
            try:
                entries = keepass_manager.get_all_entries(master_password)
                print(f"   Found {len(entries)} entries in database")
                if entries:
                    print("   First few entries:")
                    for entry in entries[:5]:
                        print(f"     - {entry}")
                return True
            except Exception as e:
                print(f"   ⚠️  Could not list entries: {e}")
                return False
                
        else:
            print("   ❌ Password rejected! Check your master password")
            return False
            
    except KeyboardInterrupt:
        print("\n   Test cancelled by user")
        return False
    except Exception as e:
        print(f"   ❌ Error during password test: {e}")
        return False

def main():
    """Main test function."""
    try:
        success = test_keepassxc_setup()
        print(f"\n=== Test Result: {'PASSED' if success else 'FAILED'} ===")
        return 0 if success else 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())