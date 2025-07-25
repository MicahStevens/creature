#!/usr/bin/env python3
"""
KeePassXC integration manager for Creature Browser.
Provides communication with KeePassXC via keepassxc-cli.
"""

import subprocess
import json
import os
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from creature_config import config as creature_config


class KeePassXCError(Exception):
    """Exception raised for KeePassXC-related errors."""
    pass


class KeePassXCEntry:
    """Represents a KeePassXC database entry."""
    
    def __init__(self, title: str, username: str = "", password: str = "", 
                 url: str = "", notes: str = "", group: str = ""):
        self.title = title
        self.username = username
        self.password = password
        self.url = url
        self.notes = notes
        self.group = group
    
    def __str__(self):
        return f"{self.title} ({self.username})"
    
    def __repr__(self):
        return f"KeePassXCEntry(title='{self.title}', username='{self.username}')"


class KeePassXCManager:
    """Manages communication with KeePassXC via keepassxc-cli."""
    
    def __init__(self):
        self.config = creature_config.keepassxc
        self._database_unlocked = False
        self._last_master_password = None
        
    @property
    def enabled(self) -> bool:
        """Check if KeePassXC integration is enabled and available."""
        return (self.config.enabled and 
                self.config.database_path and 
                self._is_cli_available())
    
    def _is_cli_available(self) -> bool:
        """Check if keepassxc-cli is available on the system."""
        try:
            result = subprocess.run(['keepassxc-cli', '--version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _expand_path(self, path: str) -> str:
        """Expand ~ and environment variables in file paths."""
        if not path:
            return ""
        expanded = str(Path(path).expanduser().resolve())
        print(f"[KeePassXC DEBUG] Path expansion: '{path}' -> '{expanded}'")
        return expanded
    
    def _run_cli_command(self, command: List[str], master_password: str = None) -> Tuple[bool, str, str]:
        """
        Run a keepassxc-cli command and return (success, stdout, stderr).
        
        Args:
            command: List of command arguments
            master_password: Master password for the database
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        if not self._is_cli_available():
            raise KeePassXCError("keepassxc-cli is not available")
        
        database_path = self._expand_path(self.config.database_path)
        if not database_path or not os.path.exists(database_path):
            raise KeePassXCError(f"Database file not found: {database_path}")
        
        # Build command with database path - some commands need database before arguments
        if len(command) > 1 and command[0] in ['search', 'show']:
            # For search/show commands: keepassxc-cli <command> <database> <arguments>
            full_command = ['keepassxc-cli', command[0], database_path] + command[1:]
        else:
            # For other commands: keepassxc-cli <command> <database>
            full_command = ['keepassxc-cli'] + command + [database_path]
        
        # Add key file if specified
        if self.config.key_file:
            key_file_path = self._expand_path(self.config.key_file)
            if os.path.exists(key_file_path):
                full_command.extend(['--key-file', key_file_path])
                print(f"[KeePassXC DEBUG] Using key file: {key_file_path}")
        
        # Debug output
        print(f"[KeePassXC DEBUG] Executing command: {' '.join(full_command[:-1])} <database>")
        print(f"[KeePassXC DEBUG] Database path: {database_path}")
        print(f"[KeePassXC DEBUG] Password provided: {'Yes' if master_password else 'No'}")
        if master_password:
            print(f"[KeePassXC DEBUG] Password length: {len(master_password)} characters")
        
        try:
            # Remove quiet mode for debugging
            if '--quiet' in full_command:
                full_command.remove('--quiet')
            
            process = subprocess.Popen(
                full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send master password if provided
            input_data = master_password + '\n' if master_password else None
            try:
                stdout, stderr = process.communicate(input=input_data, timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise KeePassXCError("KeePassXC command timed out")
            
            success = process.returncode == 0
            
            # Debug output
            print(f"[KeePassXC DEBUG] Return code: {process.returncode}")
            print(f"[KeePassXC DEBUG] Success: {success}")
            if stdout:
                print(f"[KeePassXC DEBUG] STDOUT: {stdout}")
            if stderr:
                print(f"[KeePassXC DEBUG] STDERR: {stderr}")
            
            return success, stdout.strip(), stderr.strip()
            
        except subprocess.TimeoutExpired:
            process.kill()
            print("[KeePassXC DEBUG] Command timed out!")
            raise KeePassXCError("KeePassXC command timed out")
        except Exception as e:
            print(f"[KeePassXC DEBUG] Exception: {e}")
            raise KeePassXCError(f"Failed to run KeePassXC command: {e}")
    
    def test_database_access(self, master_password: str) -> bool:
        """
        Test if we can access the database with the given master password.
        
        Args:
            master_password: Master password to test
            
        Returns:
            True if database can be accessed
        """
        print(f"[KeePassXC DEBUG] Testing database access...")
        try:
            success, stdout, stderr = self._run_cli_command(['ls'], master_password)
            if success:
                print(f"[KeePassXC DEBUG] Database access successful!")
                self._database_unlocked = True
                self._last_master_password = master_password
                return True
            else:
                print(f"[KeePassXC DEBUG] Database access failed!")
                if stderr and "invalid credentials" in stderr.lower():
                    print(f"[KeePassXC DEBUG] Invalid credentials detected")
                return False
        except KeePassXCError as e:
            print(f"[KeePassXC DEBUG] Exception during database access test: {e}")
            return False
    
    def search_entries(self, search_term: str, master_password: str = None) -> List[KeePassXCEntry]:
        """
        Search for entries matching the given term.
        
        Args:
            search_term: Search term (URL, title, etc.)
            master_password: Master password for database access
            
        Returns:
            List of matching KeePassXCEntry objects
        """
        if not self.enabled:
            return []
        
        # Use cached password if available
        if not master_password and self._last_master_password:
            master_password = self._last_master_password
        
        if not master_password:
            raise KeePassXCError("Master password required")
        
        try:
            success, stdout, stderr = self._run_cli_command(
                ['search', search_term], master_password
            )
            
            if not success:
                if "Invalid credentials" in stderr:
                    self._database_unlocked = False
                    self._last_master_password = None
                    raise KeePassXCError("Invalid master password")
                raise KeePassXCError(f"Search failed: {stderr}")
            
            # Parse search results
            entries = []
            for line in stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('==='):
                    # Simple parsing - entry names are typically shown as-is
                    entries.append(KeePassXCEntry(title=line))
            
            return entries
            
        except KeePassXCError:
            raise
        except Exception as e:
            raise KeePassXCError(f"Search error: {e}")
    
    def get_entry_details(self, entry_title: str, master_password: str = None) -> Optional[KeePassXCEntry]:
        """
        Get detailed information for a specific entry.
        
        Args:
            entry_title: Title/name of the entry
            master_password: Master password for database access
            
        Returns:
            KeePassXCEntry with full details or None if not found
        """
        if not self.enabled:
            return None
        
        # Use cached password if available
        if not master_password and self._last_master_password:
            master_password = self._last_master_password
        
        if not master_password:
            raise KeePassXCError("Master password required")
        
        try:
            success, stdout, stderr = self._run_cli_command(
                ['show', entry_title, '--show-protected'], master_password
            )
            
            if not success:
                if "Invalid credentials" in stderr:
                    self._database_unlocked = False
                    self._last_master_password = None
                    raise KeePassXCError("Invalid master password")
                return None
            
            # Parse entry details
            entry_data = {
                'title': entry_title,
                'username': '',
                'password': '',
                'url': '',
                'notes': '',
                'group': ''
            }
            
            current_section = None
            for line in stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Parse key-value pairs
                if ':' in line and not line.startswith(' '):
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == 'title':
                        entry_data['title'] = value
                    elif key in ['username', 'login']:
                        entry_data['username'] = value
                    elif key == 'password':
                        entry_data['password'] = value
                    elif key == 'url':
                        entry_data['url'] = value
                    elif key in ['notes', 'comments']:
                        entry_data['notes'] = value
                    elif key == 'group':
                        entry_data['group'] = value
            
            return KeePassXCEntry(**entry_data)
            
        except KeePassXCError:
            raise
        except Exception as e:
            raise KeePassXCError(f"Failed to get entry details: {e}")
    
    def search_by_url(self, url: str, master_password: str = None) -> List[KeePassXCEntry]:
        """
        Search for entries matching a URL domain.
        
        Args:
            url: URL to search for
            master_password: Master password for database access
            
        Returns:
            List of matching entries
        """
        if not url:
            return []
        
        try:
            # Extract domain from URL
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove common prefixes
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Search for entries matching the domain
            entries = self.search_entries(domain, master_password)
            
            # Also try searching for the full domain with www
            if not entries and not parsed.netloc.startswith('www.'):
                entries = self.search_entries(f"www.{domain}", master_password)
            
            return entries
            
        except Exception as e:
            print(f"URL search error: {e}")
            return []
    
    def copy_to_clipboard(self, entry_title: str, attribute: str = 'password', 
                         master_password: str = None, timeout: int = None) -> bool:
        """
        Copy an entry attribute to the clipboard.
        
        Args:
            entry_title: Title of the entry
            attribute: Attribute to copy (password, username, etc.)
            master_password: Master password for database access
            timeout: Clipboard timeout in seconds (uses config default if None)
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        # Use cached password if available
        if not master_password and self._last_master_password:
            master_password = self._last_master_password
        
        if not master_password:
            raise KeePassXCError("Master password required")
        
        if timeout is None:
            timeout = self.config.clip_timeout
        
        try:
            command = ['clip', entry_title]
            if attribute != 'password':
                command.extend(['--attribute', attribute])
            
            # Add timeout
            command.append(str(timeout))
            
            success, stdout, stderr = self._run_cli_command(command, master_password)
            return success
            
        except Exception as e:
            print(f"Clipboard copy error: {e}")
            return False
    
    def get_all_entries(self, master_password: str = None) -> List[str]:
        """
        Get a list of all entry titles in the database.
        
        Args:
            master_password: Master password for database access
            
        Returns:
            List of entry titles
        """
        if not self.enabled:
            return []
        
        # Use cached password if available
        if not master_password and self._last_master_password:
            master_password = self._last_master_password
        
        if not master_password:
            raise KeePassXCError("Master password required")
        
        try:
            success, stdout, stderr = self._run_cli_command(['ls'], master_password)
            
            if not success:
                if "Invalid credentials" in stderr:
                    self._database_unlocked = False
                    self._last_master_password = None
                    raise KeePassXCError("Invalid master password")
                return []
            
            # Parse entry list
            entries = []
            for line in stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('===') and '/' in line:
                    # Extract entry name from path (Group/EntryName format)
                    entry_name = line.split('/')[-1]
                    if entry_name:
                        entries.append(entry_name)
            
            return sorted(entries)
            
        except KeePassXCError:
            raise
        except Exception as e:
            raise KeePassXCError(f"Failed to list entries: {e}")


# Global instance
keepass_manager = KeePassXCManager()