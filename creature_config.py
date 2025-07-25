import logging
import os
from pathlib import Path
from collections.abc import Iterator, KeysView, ValuesView

from configobj import ConfigObj, Section
from validate import Validator

logger = logging.getLogger(__name__)


class ConfigSection:
    """Wrapper for ConfigObj sections to support dot notation access."""

    def __init__(self, section: Section) -> None:
        """Initialize with a ConfigObj section.

        Args:
            section: ConfigObj Section instance to wrap
        """
        self._section = section

    def __getattr__(self, name: str) -> list | str | int | float | dict:
        """Get configuration value using dot notation.

        Args:
            name: Configuration key name

        Returns:
            The configuration value (wrapped in ConfigSection if it's a nested section)

        Raises:
            AttributeError: If the key doesn't exist or starts with '_'
        """
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        value = self._section.get(name)
        if value is None:
            raise AttributeError(f"No configuration key '{name}'")

        # Wrap nested sections
        if isinstance(value, Section):
            return ConfigSection(value)

        return value

    def __getitem__(self, key: str) -> list | str | int | float | dict:
        """Support dictionary-style access too.

        Args:
            key: Configuration key to retrieve

        Returns:
            The configuration value for the given key
        """
        value = self._section[key]
        if isinstance(value, Section):
            return ConfigSection(value)
        return value

    def __setitem__(self, key: str, value: list | str | int | float | dict) -> None:
        """Support dictionary-style setting.

        Args:
            key: Configuration key to set
            value: Value to set for the key
        """
        self._section[key] = value

    def get(self, key: str, default: list | str | int | float | dict = None) -> list | str | int | float | dict:
        """Get with default value.

        Args:
            key: Configuration key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The configuration value or default if not found
        """
        return self._section.get(key, default)

    def items(self) -> Iterator[tuple[str, list | str | int | float | dict]]:
        """Iterate over items.

        Returns:
            Iterator of (key, value) tuples
        """
        return self._section.items()

    def keys(self) -> KeysView[str]:
        """Get keys.

        Returns:
            View of configuration keys
        """
        return self._section.keys()

    def values(self) -> ValuesView[list | str | int | float | dict]:
        """Get values.

        Returns:
            View of configuration values
        """
        return self._section.values()
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in section.
        
        Args:
            key: Key to check
            
        Returns:
            True if key exists
        """
        return key in self._section


class CreatureConfig:
    """
    Configuration manager for Creature browser.

    Provides dot-notation access to configuration values loaded from INI files.
    Searches for config files in order of precedence: environment variable,
    user config directory, and current directory.

    Example:
        config = CreatureConfig()
        # Access values using dot notation
        theme = config.general.theme
        width = config.window.width
        config.general.home_page = 'https://example.com'
    """

    def __init__(self) -> None:
        """Initialize configuration by loading from config file."""
        configfile = self._get_config_path()
        self._config_file_path = configfile  # Store path for access

        # Load config with validation against spec
        spec_path = Path(__file__).parent / 'config.spec'
        if spec_path.exists():
            # Load config with spec validation, but handle profiles separately
            self._config = ConfigObj(str(configfile), configspec=str(spec_path))
            validator = Validator()
            
            # Validate config - this will apply defaults
            self._config.validate(validator, preserve_errors=True)
            
            # Ensure profiles section exists (not validated by spec)
            if 'profiles' not in self._config:
                self._config['profiles'] = {}
            
            # Write config to ensure all defaults are saved
            self._config.write()
            
            logger.info(f"Loaded configuration with validation from: {configfile}")
        else:
            self._config = ConfigObj(str(configfile))
            logger.warning(f"Config spec not found at {spec_path}, loaded without validation from: {configfile}")

    def __getattr__(self, name: str) -> list | str | int | float | dict:
        """Get configuration value using dot notation.

        Args:
            name: Configuration key name

        Returns:
            The configuration value (wrapped in ConfigSection if it's a nested section)

        Raises:
            AttributeError: If the key doesn't exist or starts with '_'
        """
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        value = self._config.get(name)
        if value is None:
            raise AttributeError(f"No configuration key '{name}'")

        # Wrap sections to support dot notation
        if isinstance(value, Section):
            return ConfigSection(value)

        return value

    def __setattr__(self, name: str, value: list | str | int | float | dict) -> None:
        """Set configuration value using dot notation.

        Args:
            name: Configuration key name or instance attribute name
            value: Value to set
        """
        if name.startswith('_') or name in ['get_config_path']:
            super().__setattr__(name, value)
        else:
            self._config[name] = value

    def _get_config_path(self) -> Path:
        """Find configuration file in order of precedence.

        Returns:
            Path: Path object of the first existing config file

        Raises:
            FileNotFoundError: If no config file found (should not happen with default)
        """
        search_locations = []

        # Environment variable
        if env_path := os.environ.get('CREATURE_CONFIG'):
            search_locations.append(Path(env_path))

        # User config directory
        user_config_dir = Path.home() / '.config' / 'creature'
        search_locations.append(user_config_dir / 'config.ini')

        # Current directory
        search_locations.append(Path('config.ini'))

        # Find first existing file
        for config_path in search_locations:
            if config_path.exists():
                logger.info(f"Using config file: {config_path}")
                return config_path
            logger.debug(f"Config not found at: {config_path}")

        # Create default config in user directory if none exists
        user_config_dir.mkdir(parents=True, exist_ok=True)
        default_path = user_config_dir / 'config.ini'
        
        # Create empty config that will be populated with defaults
        default_path.touch()
        logger.info(f"Created new config file at: {default_path}")
        return default_path

    def save(self) -> None:
        """Save current configuration to file."""
        self._config.write()

    def reload(self) -> None:
        """Reload configuration from file."""
        self.__init__()
    
    @property
    def config_file_path(self) -> Path:
        """Get the path to the currently loaded configuration file.
        
        Returns:
            Path: Path object to the configuration file
        """
        return self._config_file_path


# Create singleton instance
config = CreatureConfig()