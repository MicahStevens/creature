"""
History management module for Creature Browser.
Provides per-profile browsing history with autocomplete functionality.
"""

from .manager import HistoryManager
from .database import HistoryDatabase

__all__ = ["HistoryManager", "HistoryDatabase"]
