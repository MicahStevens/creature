"""
Profile management for Creature Browser.
Manages browser profiles with separate storage, settings, and permissions.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineSettings, QWebEnginePage, 
    QWebEnginePermission
)

from creature.config.manager import config as creature_config

logger = logging.getLogger(__name__)


class ProfileManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = Path.home() / ".config" / "creature"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_profile_path(self, profile_name):
        profile_path = self.base_dir / f"profile_{profile_name}"
        profile_path.mkdir(exist_ok=True)
        return str(profile_path)
    
    def list_profiles(self):
        """List all existing profiles."""
        profiles = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and item.name.startswith("profile_"):
                profile_name = item.name.replace("profile_", "")
                profiles.append(profile_name)
        return sorted(profiles) if profiles else ["default"]

    def create_profile(self, profile_name):
        profile_path = self.get_profile_path(profile_name)

        # Create profile with unique name
        profile = QWebEngineProfile(f"profile_{profile_name}")
        profile.setPersistentStoragePath(profile_path)
        profile.setCachePath(profile_path + "/cache")
        
        # Store profile name for permission handler
        profile.profile_name = profile_name
        
        # Debug: Check for profile-level permission handling
        logger.debug("=== QWebEngineProfile available attributes ===")
        for attr in sorted(dir(profile)):
            if 'permission' in attr.lower() or 'feature' in attr.lower():
                logger.debug(f"Profile has attribute: {attr}")
        
        # Set up modern permission handling using profile permission policy
        try:
            # Set persistent permissions policy to ask for each permission
            if hasattr(profile, 'setPersistentPermissionsPolicy'):
                profile.setPersistentPermissionsPolicy(profile.PersistentPermissionsPolicy.AskEveryTime)
                logger.info("Set persistent permissions policy to AskEveryTime")
            
            # Auto-grant common permissions for debugging
            self._setup_auto_permissions(profile, profile_name)
            
            # Feature permission is handled at page level, not profile level
            logger.info("Feature permission handling will be done at page level")
            
        except Exception as e:
            logger.error(f"Could not set up permission policy: {e}")

        # Enable features from config
        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, 
                            creature_config.browser.javascript_enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, 
                            creature_config.browser.local_storage_enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, 
                            creature_config.browser.plugins_enabled)
        
        # Get profile-specific WebRTC settings
        screen_capture_enabled = self.get_profile_setting(profile_name, 'screen_capture_enabled', True)
        
        # Enable WebRTC features for camera/microphone support based on profile config
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, screen_capture_enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, False)
        
        # Additional stability settings for media device switching
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        
        # Enable WebGL but disable problematic 2D canvas acceleration 
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)  # Disabled to prevent black screens
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        
        # Set a proper Chrome user agent for Google Meet compatibility
        profile.setHttpUserAgent(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Permission handling is done through web pages, not profiles

        return profile
    
    def get_profile_setting(self, profile_name, setting_name, default_value):
        """Get a profile-specific setting with fallback to default."""
        try:
            if hasattr(creature_config, 'profiles') and profile_name in creature_config.profiles:
                profile_config = creature_config.profiles[profile_name]
                return profile_config.get(setting_name, default_value)
        except Exception as e:
            logger.debug(f"Error getting profile setting {setting_name} for {profile_name}: {e}")
        
        return default_value
    
    def _setup_auto_permissions(self, profile, profile_name):
        """Set up automatic permission granting for debugging."""
        try:
            # Common sites that need camera/microphone
            sites_to_grant = [
                "https://meet.google.com",
                "https://zoom.us", 
                "https://teams.microsoft.com",
                "https://discord.com",
                "https://whereby.com"
            ]
            
            # Permission types to auto-grant (using correct enum names)
            permissions_to_grant = [
                "Camera", "Microphone", "MediaAudioCapture", 
                "MediaVideoCapture", "MediaAudioVideoCapture"
            ]
            
            logger.info("Auto-granting permissions for common video conferencing sites...")
            
            # Debug: List available permission types
            logger.debug("=== Available Permission Types ===")
            for attr in sorted(dir(QWebEnginePermission.PermissionType)):
                if not attr.startswith('_'):
                    logger.debug(f"Permission type: {attr}")
            
            # Debug: Check QWebEnginePermission constructor
            logger.debug("=== QWebEnginePermission Constructor Info ===")
            try:
                # Try to create empty permission to see constructor signature
                test_perm = QWebEnginePermission()
                logger.debug("Empty QWebEnginePermission constructor works")
            except Exception as e:
                logger.debug(f"Empty constructor failed: {e}")
            
            # Skip auto-granting individual permissions since QWebEnginePermission 
            # objects must be created by the browser engine, not manually
            logger.info("Permissions will be auto-granted when requested by the page")
                        
        except Exception as e:
            logger.error(f"Error setting up auto-permissions: {e}")
    
    def _handle_feature_permission(self, url, feature, profile, profile_name):
        """Handle feature permission requests at profile level."""
        logger.debug(f"PROFILE FEATURE PERMISSION REQUEST!")
        logger.debug(f"URL: {url.toString()}")
        logger.debug(f"Feature: {feature}")
        logger.debug(f"Profile: {profile_name}")
        
        # DISABLED: Let page-level handler show dialog instead of auto-granting
        logger.debug("Profile-level auto-granting disabled - delegating to page-level handler")
        return
        
        # Original auto-granting code (commented out)
        # try:
        #     # Auto-grant the feature permission  
        #     profile.setPermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
        #     logger.info(f"AUTO-GRANTED feature {feature} for {url.toString()}")
        # except Exception as e:
        #     logger.error(f"Error granting feature permission: {e}")
    
    def get_stored_permission(self, profile_name, origin, permission_type):
        """Get stored permission for a site and permission type."""
        try:
            if hasattr(creature_config, 'profiles') and profile_name in creature_config.profiles:
                profile_config = creature_config.profiles[profile_name]
                permissions_key = f"permissions_{origin.replace('.', '_')}"
                
                if permissions_key in profile_config:
                    site_permissions = profile_config[permissions_key]
                    return site_permissions.get(str(permission_type.value), None)
        except Exception as e:
            logger.debug(f"Error getting stored permission: {e}")
        
        return None
    
    def save_permission(self, profile_name, origin, permission_type, granted):
        """Save permission decision to config."""
        try:
            # Ensure the profile section exists
            if not hasattr(creature_config, 'profiles'):
                creature_config._config['profiles'] = {}
            
            if profile_name not in creature_config.profiles:
                creature_config._config['profiles'][profile_name] = {}
            
            # Create permissions key for this origin
            permissions_key = f"permissions_{origin.replace('.', '_')}"
            
            # Get or create the permissions section for this site
            profile_section = creature_config._config['profiles'][profile_name]
            if permissions_key not in profile_section:
                profile_section[permissions_key] = {}
            
            # Store the permission decision
            profile_section[permissions_key][str(permission_type.value)] = granted
            
            # Save the config
            creature_config.save()
            logger.info(f"Saved permission {permission_type} = {granted} for {origin} in profile {profile_name}")
            
        except Exception as e:
            logger.error(f"Error saving permission: {e}")
    
    def handle_permission_request(self, permission, profile_name):
        """Handle permission requests for camera, microphone, etc."""
        # This method is a placeholder - actual handling is done at page level
        logger.debug(f"Permission request in profile {profile_name}: {permission}")
        # Delegate to page-level handler