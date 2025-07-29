"""
Creature Browser - A PyQt6-based web browser with profile support.

This package provides a feature-rich web browser built on PyQt6 with support for:
- Multiple user profiles
- Bookmark management with hierarchical organization
- Theme support
- KeePassXC integration
- SSL certificate management
"""

__version__ = "0.1.0"
__author__ = "micah@benchtop.tech"
__license__ = "MIT"

# Application constants
CREATURE_VERSION = __version__
CREATURE_AUTHOR = __author__
CREATURE_LICENSE = __license__


def main():
    """Entry point for the Creature browser application."""
    from creature.browser.main import main as browser_main
    return browser_main()