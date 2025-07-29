"""
Custom WebEngine classes for Creature Browser.
Contains SSLAwarePage and other custom page implementations.
"""

import logging

from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class SSLAwarePage(QWebEnginePage):
    """Custom QWebEnginePage that handles SSL certificate information."""
    
    sslStatusChanged = pyqtSignal(dict)
    
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.ssl_info = {
            'is_secure': False,
            'certificate_valid': True,
            'certificate_info': None,
            'errors': []
        }
        self.profile_name = getattr(profile, 'profile_name', 'default')
        self._profile_ref = profile  # Keep reference to prevent premature cleanup
        
        # Debug: List all available signals/methods
        logger.debug("=== QWebEnginePage available attributes ===")
        for attr in sorted(dir(self)):
            if 'permission' in attr.lower() or 'feature' in attr.lower():
                logger.debug(f"Found attribute: {attr}")
        
        # Connect permission request handler
        try:
            # Try the standard signal name
            self.permissionRequested.connect(self.handle_permission_request)
            logger.info("Connected to permissionRequested signal")
        except AttributeError:
            logger.error("Could not connect to permissionRequested signal!")
        
        # ALSO try feature permission signal
        try:
            self.featurePermissionRequested.connect(self.handle_feature_permission_request)
            logger.info("Connected to featurePermissionRequested signal")
        except AttributeError:
            logger.debug("featurePermissionRequested not available")
        
        # Connect to JavaScript console messages
        try:
            self.javaScriptConsoleMessage.connect(self._on_javascript_console_message)
            logger.debug("Connected to JavaScript console message handler")
        except AttributeError:
            logger.debug("JavaScript console message handler not available")
        
        # Store original setFeaturePermission method
        self._original_setFeaturePermission = self.setFeaturePermission
        
        # Override setFeaturePermission to intercept calls
        def intercepted_setFeaturePermission(securityOrigin, feature, policy):
            logger.debug(f"🔍 INTERCEPTED setFeaturePermission call!")
            logger.debug(f"🌐 Security Origin: {securityOrigin.toString()}")
            logger.debug(f"🎥 Feature: {feature}")
            logger.debug(f"📋 Policy: {policy}")
            return self._original_setFeaturePermission(securityOrigin, feature, policy)
        
        self.setFeaturePermission = intercepted_setFeaturePermission
        
        # Also add a load finished handler to monitor page activity
        self.loadFinished.connect(self._on_load_finished)
        
        # Add more debugging signals
        try:
            # Monitor all possible permission-related signals
            if hasattr(self, 'permissionRequested'):
                # Add a lambda to capture all args
                self.permissionRequested.connect(lambda *args: logger.debug(f"🚨 permissionRequested signal triggered with args: {args}"))
            
            if hasattr(self, 'featurePermissionRequested'):
                # Add a lambda to capture all args  
                self.featurePermissionRequested.connect(lambda *args: logger.debug(f"🚨 featurePermissionRequested signal triggered with args: {args}"))
                
            # Try to connect to profile-level signals if they exist
            profile = self.profile()
            if profile and hasattr(profile, 'permissionRequested'):
                profile.permissionRequested.connect(lambda *args: logger.debug(f"🚨 PROFILE permissionRequested signal triggered with args: {args}"))
                
        except Exception as e:
            logger.debug(f"Error setting up debug signals: {e}")
        
        # Add JavaScript injection to monitor media API calls
        self._inject_media_debug_script()
    
    def certificateError(self, error):
        """Handle SSL certificate errors and extract certificate information."""
        logger.debug(f"Certificate error detected: {error.description()}")
        
        cert_info = {
            'error_type': error.error(),
            'description': error.description(),
            'url': error.url().toString(),
            'is_overridable': error.isOverridable(),
            'certificate_chain': []
        }
        
        # Extract certificate details from chain
        cert_chain = error.certificateChain()
        logger.debug(f"Certificate chain length: {len(cert_chain)}")
        
        for i, cert in enumerate(cert_chain):
            logger.debug(f"Processing certificate {i+1}")
            cert_details = {
                'subject': cert.subjectDisplayName(),
                'issuer': cert.issuerDisplayName(),
                'expiry_date': cert.expiryDate().toString(),
                'effective_date': cert.effectiveDate().toString(),
                'is_self_signed': cert.isSelfSigned(),
                'serial_number': cert.serialNumber().toHex().data().decode('utf-8') if cert.serialNumber().toHex() else 'N/A',
                'version': str(cert.version()) if hasattr(cert, 'version') else 'N/A'
            }
            cert_info['certificate_chain'].append(cert_details)
            logger.debug(f"Certificate {i+1} subject: {cert_details['subject']}")
        
        # Update SSL status
        self.ssl_info.update({
            'certificate_valid': False,  # If this method is called, there's an error
            'certificate_info': cert_info,
            'errors': [cert_info]
        })
        
        logger.debug(f"Emitting SSL status: {self.ssl_info}")
        self.sslStatusChanged.emit(self.ssl_info)
        
        # Return True to accept certificate (override error) or False to reject
        # For now, accept overridable errors but mark as invalid
        return error.isOverridable()
    
    def handle_permission_request(self, permission):
        """Handle permission requests for this page."""
        logger.debug(f"SSLAwarePage.handle_permission_request called!")
        try:
            # Check if permission is still valid/pending to avoid duplicate processing
            if not permission:
                logger.debug("Permission is None, skipping")
                return
                
            logger.debug(f"Permission state: {permission.state()}")
            # DISABLED: Don't skip based on state - handle all permission requests
            # We want to show dialogs even if something else auto-granted them
            # try:
            #     if hasattr(permission, 'State') and permission.state() != permission.State.Requested:
            #         logger.debug(f"Permission request not in requested state ({permission.state()}), skipping")
            #         return
            # except AttributeError:
            #     # Skip state check if State enum is not accessible
            #     pass
                
            permission_type = permission.permissionType()
            origin = permission.origin().host()
            logger.debug(f"SSLAwarePage handling permission request: {permission_type} for {origin}")
            
            # Get the main browser instance to access ProfileManager
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'profile_manager'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'profile_manager'):
                main_window.profile_manager.handle_permission_request(permission, self.profile_name)
            else:
                logger.error("Could not find ProfileManager to handle permission request")
                permission.grant()  # Default to grant if we can't find the manager
        except Exception as e:
            logger.error(f"Error handling permission request: {e}")
            # Always respond to avoid hanging permission requests
            try:
                if permission:
                    try:
                        if hasattr(permission, 'State') and permission.state() == permission.State.Requested:
                            permission.grant()
                        else:
                            permission.grant()  # Grant anyway
                    except AttributeError:
                        permission.grant()  # Grant anyway if state check fails
            except Exception:
                pass  # Ignore errors when trying to respond
    
    def _on_load_finished(self, ok):
        """Monitor when pages finish loading."""
        current_url = self.url().toString()
        if "meet.google.com" in current_url:
            logger.info(f"📄 Google Meet page loaded: {current_url}")
            logger.info("💡 Try clicking camera/microphone buttons to trigger permission requests!")
            # Re-inject our debug script after page loads
            self._inject_media_debug_script()
            # Pre-grant permissions for Google Meet to avoid stuck requests
            self._pre_grant_google_meet_permissions()
    
    def _inject_media_debug_script(self):
        """Inject JavaScript to monitor getUserMedia calls."""
        js_code = """
        // Override getUserMedia to log when it's called
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
            navigator.mediaDevices.getUserMedia = function(constraints) {
                console.log('🎥 getUserMedia called with constraints:', constraints);
                console.log('🚨 JavaScript: Media permission being requested!');
                return originalGetUserMedia(constraints).then(stream => {
                    console.log('✅ getUserMedia successful, stream:', stream);
                    return stream;
                }).catch(error => {
                    console.log('❌ getUserMedia failed:', error);
                    throw error;
                });
            };
            console.log('🔧 getUserMedia monitoring injected');
        } else {
            console.log('❌ getUserMedia not available');
        }
        
        // Also check for older getUserMedia API
        if (navigator.getUserMedia) {
            const originalGetUserMedia2 = navigator.getUserMedia.bind(navigator);
            navigator.getUserMedia = function(constraints, success, error) {
                console.log('🎥 Legacy getUserMedia called with constraints:', constraints);
                console.log('🚨 JavaScript: Legacy media permission being requested!');
                return originalGetUserMedia2(constraints, success, error);
            };
            console.log('🔧 Legacy getUserMedia monitoring injected');
        }
        
        // Google Meet specific: Auto-trigger permission requests and debug JS errors
        if (window.location.hostname.includes('meet.google.com')) {
            console.log('🎯 Google Meet detected - setting up debugging and auto-trigger');
            
            // Monitor JavaScript errors with more detailed logging
            window.addEventListener('error', function(e) {
                console.error('❌ JavaScript Error on Google Meet:', e.error?.stack || e.error);
                console.error('Error details - File:', e.filename, 'Line:', e.lineno, 'Col:', e.colno, 'Message:', e.message);
            });
            
            // Monitor unhandled promise rejections
            window.addEventListener('unhandledrejection', function(e) {
                console.error('❌ Unhandled Promise Rejection on Google Meet:', e.reason);
                if (e.reason?.stack) console.error('Stack:', e.reason.stack);
            });
            
            // Monitor all console methods, not just error
            const originalLog = console.log;
            const originalError = console.error;
            const originalWarn = console.warn;
            
            console.log = function(...args) {
                if (args.some(arg => typeof arg === 'string' && (arg.includes('meet') || arg.includes('Meeting')))) {
                    originalLog('🌐 Google Meet Log:', ...args);
                }
                originalLog.apply(console, args);
            };
            
            console.error = function(...args) {
                originalError('🚨 Google Meet Error:', ...args);
                originalError.apply(console, args);
            };
            
            console.warn = function(...args) {
                originalError('⚠️ Google Meet Warning:', ...args);
                originalWarn.apply(console, args);
            };
            
            // Monitor fetch/XHR requests for meeting creation
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                const url = args[0];
                console.log('🌐 Google Meet Fetch Request:', url);
                return originalFetch.apply(this, args)
                    .then(response => {
                        console.log('✅ Fetch Response:', response.status, response.url);
                        if (!response.ok) {
                            console.error('❌ Fetch failed with status:', response.status, response.statusText);
                        }
                        return response;
                    })
                    .catch(error => {
                        console.error('❌ Fetch Error:', error);
                        throw error;
                    });
            };
            
            setTimeout(() => {
                // Try to trigger permission requests
                if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    console.log('🔧 Pre-requesting camera and microphone for Google Meet...');
                    navigator.mediaDevices.getUserMedia({video: true, audio: true})
                        .then(stream => {
                            console.log('✅ Google Meet pre-request successful');
                            // Keep stream briefly then close
                            setTimeout(() => {
                                stream.getTracks().forEach(track => track.stop());
                                console.log('🔧 Pre-request streams stopped');
                            }, 100);
                        })
                        .catch(error => {
                            console.log('❌ Google Meet pre-request failed:', error);
                        });
                }
                
                // Debug: Check for common Google Meet elements
                setTimeout(() => {
                    const instantButton = document.querySelector('[data-testid="instant-meeting-button"]') || 
                                        document.querySelector('button[aria-label*="instant"]') ||
                                        document.querySelector('button[aria-label*="Instant"]');
                    if (instantButton) {
                        console.log('✅ Found instant meeting button:', instantButton);
                        instantButton.addEventListener('click', () => {
                            console.log('🎯 Instant meeting button clicked!');
                        });
                    } else {
                        console.log('❌ Could not find instant meeting button');
                    }
                }, 1000);
            }, 2000); // Wait 2 seconds for page to load
        }
        """
        
        try:
            self.runJavaScript(js_code)
            logger.info("🔧 JavaScript media monitoring injected")
        except Exception as e:
            logger.debug(f"Failed to inject JavaScript: {e}")
    
    def _pre_grant_google_meet_permissions(self):
        """Pre-grant media permissions for Google Meet to avoid stuck requests."""
        # Google Meet specifically needs pre-granting to avoid getting stuck
        # We'll show a dialog first, then pre-grant if user approves
        try:
            # Get the current URL
            current_url = self.url()
            
            # Ask user once for Google Meet permissions
            permission_granted = self._ask_user_permission(
                current_url.host(), 
                "camera and microphone for Google Meet"
            )
            
            if permission_granted:
                logger.info(f"🎯 User approved - pre-granting permissions for Google Meet: {current_url.toString()}")
                
                # Pre-grant all media features for this Google Meet URL
                media_features = [
                    QWebEnginePage.Feature.MediaAudioCapture,
                    QWebEnginePage.Feature.MediaVideoCapture, 
                    QWebEnginePage.Feature.MediaAudioVideoCapture
                ]
                
                for feature in media_features:
                    try:
                        self.setFeaturePermission(current_url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
                        logger.info(f"✅ Pre-granted {feature} for Google Meet")
                    except Exception as e:
                        logger.debug(f"Could not pre-grant {feature}: {e}")
            else:
                logger.info("❌ User denied Google Meet permissions")
                return
        except Exception as e:
            logger.error(f"Error handling Google Meet permissions: {e}")
            return
        
        # Original pre-granting code (commented out)
        # try:
        #     from PyQt6.QtCore import QUrl
        #     
        #     # Get the current URL
        #     current_url = self.url()
        #     logger.info(f"🎯 Pre-granting permissions for Google Meet: {current_url.toString()}")
        #     
        #     # Pre-grant all media features for this Google Meet URL
        #     media_features = [
        #         QWebEnginePage.Feature.MediaAudioCapture,
        #         QWebEnginePage.Feature.MediaVideoCapture, 
        #         QWebEnginePage.Feature.MediaAudioVideoCapture
        #     ]
        #     
        #     for feature in media_features:
        #         try:
        #             self.setFeaturePermission(current_url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
        #             logger.info(f"✅ Pre-granted {feature} for Google Meet")
        #         except Exception as e:
        #             logger.debug(f"Could not pre-grant {feature}: {e}")
        #                 
        #     # Also inject JavaScript to clear any stuck permission requests
        #     clear_js = """
        #     // Try to clear any stuck permission requests
        #     if (window.navigator && window.navigator.permissions) {
        #         window.navigator.permissions.query({name: 'camera'}).then(function(result) {
        #             console.log('Camera permission status:', result.state);
        #         });
        #         window.navigator.permissions.query({name: 'microphone'}).then(function(result) {
        #             console.log('Microphone permission status:', result.state);
        #         });
        #     }
        #     
        #     // Force a fresh getUserMedia call to reset state
        #     console.log('🔧 Attempting to clear stuck permissions...');
        #     """
        #     
        #     self.runJavaScript(clear_js)
        #     logger.debug("🔧 Injected permission clearing JavaScript")
        #     
        # except Exception as e:
        #     logger.error(f"Error pre-granting Google Meet permissions: {e}")
    
    def handle_feature_permission_request(self, securityOrigin, feature):
        """Handle feature permission requests using the correct PyQt pattern."""
        logger.debug(f"🎯 FEATURE PERMISSION REQUESTED!")
        logger.debug(f"🌐 Security Origin: {securityOrigin.toString()}")
        logger.debug(f"🎥 Feature: {feature}")
        logger.debug(f"📋 Feature Type: {type(feature)}")
        
        # List available features on first call
        if not hasattr(self, '_features_listed'):
            logger.debug("=== Available Features ===")
            for attr in sorted(dir(QWebEnginePage.Feature)):
                if not attr.startswith('_'):
                    feature_value = getattr(QWebEnginePage.Feature, attr)
                    logger.debug(f"Feature: {attr} = {feature_value}")
            self._features_listed = True
        
        # Show permission dialog to user instead of auto-granting
        try:
            if feature in (QWebEnginePage.Feature.MediaAudioCapture, 
                          QWebEnginePage.Feature.MediaVideoCapture, 
                          QWebEnginePage.Feature.MediaAudioVideoCapture):
                
                # Get feature name for dialog
                feature_names = {
                    QWebEnginePage.Feature.MediaAudioCapture: "microphone",
                    QWebEnginePage.Feature.MediaVideoCapture: "camera", 
                    QWebEnginePage.Feature.MediaAudioVideoCapture: "camera and microphone"
                }
                feature_name = feature_names.get(feature, "media device")
                
                # Ask user for permission
                permission_granted = self._ask_user_permission(securityOrigin.toString(), feature_name)
                
                if permission_granted:
                    self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
                    logger.info(f"✅ GRANTED {feature_name} permission to {securityOrigin.toString()}")
                else:
                    self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
                    logger.info(f"❌ DENIED {feature_name} permission to {securityOrigin.toString()}")
            else:
                # For non-media features, ask for permission too
                permission_granted = self._ask_user_permission(securityOrigin.toString(), f"feature {feature}")
                
                if permission_granted:
                    self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
                    logger.info(f"✅ GRANTED feature {feature} to {securityOrigin.toString()}")
                else:
                    self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
                    logger.info(f"❌ DENIED feature {feature} to {securityOrigin.toString()}")
        except Exception as e:
            logger.error(f"❌ Error handling feature permission: {e}")
    
    def _ask_user_permission(self, origin, feature_name):
        """Ask user for permission via dialog."""
        # Get the parent window properly
        parent_widget = None
        try:
            # Try to get the main window as parent
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, 'windowTitle'):
                parent_widget = parent_widget.parent()
        except:
            parent_widget = None
        
        # Create permission dialog
        msg_box = QMessageBox(parent_widget)
        msg_box.setWindowTitle("Permission Request")
        msg_box.setText(f"Allow {origin} to access your {feature_name}?")
        msg_box.setInformativeText(f"The website {origin} is requesting access to your {feature_name}.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        # Show dialog and get result
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes
    
    def _on_javascript_console_message(self, level, message, line, source):
        """Handle JavaScript console messages and forward to Python logging."""
        # Only log Google Meet related messages to avoid spam
        if 'meet.google.com' in source or 'Google Meet' in message or any(marker in message for marker in ['🎯', '🔧', '✅', '❌', '🚨', '🌐']):
            level_map = {
                0: "INFO",    # Info
                1: "WARNING", # Warning  
                2: "ERROR"    # Error
            }
            level_name = level_map.get(level, "DEBUG")
            logger.info(f"JS-{level_name}: {message} (line {line} in {source})")
    
    def __del__(self):
        """Proper cleanup to prevent profile/page lifecycle warnings."""
        try:
            # Disconnect all signals before destruction
            self.permissionRequested.disconnect()
            self.featurePermissionRequested.disconnect()
            self.loadFinished.disconnect()
            
            # Clear profile reference
            self._profile_ref = None
            
            logger.debug("SSLAwarePage cleanup completed")
        except Exception as e:
            logger.debug(f"SSLAwarePage cleanup error (normal during shutdown): {e}")