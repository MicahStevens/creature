/**
 * KeePassXC Bridge for Creature Browser
 * Provides form detection, filling, and interaction capabilities
 */

(function() {
    'use strict';
    
    // Prevent multiple injections
    if (window.KeePassXCBridge) {
        return;
    }
    
    // Main KeePassXC Bridge object
    window.KeePassXCBridge = {
        version: '1.0.0',
        
        /**
         * Detect all forms and input fields on the current page
         * @returns {Object} Object containing forms and inputs data
         */
        detectForms: function() {
            const forms = [];
            const inputs = [];
            
            // Detect all forms
            document.querySelectorAll('form').forEach((form, index) => {
                const formData = {
                    index: index,
                    id: form.id || '',
                    name: form.name || '',
                    action: form.action || '',
                    method: form.method || 'get',
                    className: form.className || '',
                    inputs: []
                };
                
                // Find inputs within this form
                form.querySelectorAll('input, textarea, select').forEach(input => {
                    formData.inputs.push(this._getInputInfo(input));
                });
                
                forms.push(formData);
            });
            
            // Detect all input fields (including those outside forms)
            document.querySelectorAll('input, textarea, select').forEach((input, index) => {
                inputs.push(this._getInputInfo(input, index));
            });
            
            return {
                url: window.location.href,
                domain: window.location.hostname,
                title: document.title,
                forms: forms,
                inputs: inputs,
                loginFields: this._detectLoginFields()
            };
        },
        
        /**
         * Get detailed information about an input element
         * @param {Element} input - The input element
         * @param {number} index - Index of the input
         * @returns {Object} Input information
         */
        _getInputInfo: function(input, index = null) {
            return {
                index: index,
                tagName: input.tagName.toLowerCase(),
                type: input.type || '',
                id: input.id || '',
                name: input.name || '',
                className: input.className || '',
                placeholder: input.placeholder || '',
                value: input.value || '',
                required: input.required || false,
                disabled: input.disabled || false,
                readonly: input.readOnly || false,
                autocomplete: input.autocomplete || '',
                maxlength: input.maxLength || null,
                visible: this._isVisible(input),
                isPasswordField: input.type === 'password',
                isEmailField: this._isEmailField(input),
                isUsernameField: this._isUsernameField(input),
                isLoginForm: this._isInLoginForm(input)
            };
        },
        
        /**
         * Detect login-related fields automatically
         * @returns {Object} Login fields information
         */
        _detectLoginFields: function() {
            const usernameFields = [];
            const passwordFields = [];
            const emailFields = [];
            
            document.querySelectorAll('input').forEach(input => {
                if (!this._isVisible(input)) {
                    return;
                }
                
                if (input.type === 'password') {
                    passwordFields.push(this._getInputInfo(input));
                } else if (this._isEmailField(input)) {
                    emailFields.push(this._getInputInfo(input));
                } else if (this._isUsernameField(input)) {
                    usernameFields.push(this._getInputInfo(input));
                }
            });
            
            return {
                username: usernameFields,
                password: passwordFields,
                email: emailFields,
                hasLoginForm: passwordFields.length > 0 && (usernameFields.length > 0 || emailFields.length > 0)
            };
        },
        
        /**
         * Check if an input field is visible
         * @param {Element} element - The element to check
         * @returns {boolean} True if visible
         */
        _isVisible: function(element) {
            const style = window.getComputedStyle(element);
            return style.display !== 'none' && 
                   style.visibility !== 'hidden' && 
                   style.opacity !== '0' &&
                   element.offsetWidth > 0 && 
                   element.offsetHeight > 0;
        },
        
        /**
         * Check if an input field is likely an email field
         * @param {Element} input - The input element
         * @returns {boolean} True if likely an email field
         */
        _isEmailField: function(input) {
            if (input.type === 'email') {
                return true;
            }
            
            const patterns = [
                /email/i, /e-mail/i, /mail/i, /@/
            ];
            
            const testString = (input.name + ' ' + input.id + ' ' + input.placeholder + ' ' + input.className).toLowerCase();
            return patterns.some(pattern => pattern.test(testString));
        },
        
        /**
         * Check if an input field is likely a username field
         * @param {Element} input - The input element
         * @returns {boolean} True if likely a username field
         */
        _isUsernameField: function(input) {
            if (input.type === 'password' || input.type === 'email') {
                return false;
            }
            
            const patterns = [
                /user/i, /login/i, /account/i, /member/i, /customer/i, /client/i
            ];
            
            const testString = (input.name + ' ' + input.id + ' ' + input.placeholder + ' ' + input.className).toLowerCase();
            return patterns.some(pattern => pattern.test(testString));
        },
        
        /**
         * Check if an input is part of a login form
         * @param {Element} input - The input element
         * @returns {boolean} True if in login form
         */
        _isInLoginForm: function(input) {
            const form = input.closest('form');
            if (!form) {
                return false;
            }
            
            // Check if form contains password field
            const hasPasswordField = form.querySelector('input[type="password"]') !== null;
            
            // Check form attributes for login indicators
            const formString = (form.action + ' ' + form.id + ' ' + form.className).toLowerCase();
            const loginPatterns = [/login/i, /signin/i, /auth/i, /session/i];
            const hasLoginPattern = loginPatterns.some(pattern => pattern.test(formString));
            
            return hasPasswordField || hasLoginPattern;
        },
        
        /**
         * Fill a specific input field with a value
         * @param {string|Element} selector - CSS selector or element
         * @param {string} value - Value to fill
         * @param {boolean} triggerEvents - Whether to trigger change events
         * @returns {boolean} True if successful
         */
        fillField: function(selector, value, triggerEvents = true) {
            try {
                let element;
                if (typeof selector === 'string') {
                    element = document.querySelector(selector);
                } else {
                    element = selector;
                }
                
                if (!element) {
                    console.warn('KeePassXC Bridge: Element not found:', selector);
                    return false;
                }
                
                // Focus the element first
                element.focus();
                
                // Set the value
                element.value = value;
                
                // Trigger events to notify frameworks (React, Vue, etc.)
                if (triggerEvents) {
                    this._triggerEvents(element);
                }
                
                return true;
            } catch (error) {
                console.error('KeePassXC Bridge: Fill field error:', error);
                return false;
            }
        },
        
        /**
         * Fill login form with username and password
         * @param {string} username - Username to fill
         * @param {string} password - Password to fill
         * @param {boolean} autoSubmit - Whether to auto-submit the form
         * @returns {Object} Result of the fill operation
         */
        fillLoginForm: function(username, password, autoSubmit = false) {
            const result = {
                success: false,
                usernameFilled: false,
                passwordFilled: false,
                submitted: false,
                errors: []
            };
            
            try {
                const loginFields = this._detectLoginFields();
                
                // Fill username/email field
                if (username) {
                    let usernameField = null;
                    
                    // Try email field first, then username
                    if (loginFields.email.length > 0) {
                        usernameField = document.querySelector(`#${loginFields.email[0].id}`) || 
                                      document.querySelector(`[name="${loginFields.email[0].name}"]`);
                    } else if (loginFields.username.length > 0) {
                        usernameField = document.querySelector(`#${loginFields.username[0].id}`) || 
                                      document.querySelector(`[name="${loginFields.username[0].name}"]`);
                    }
                    
                    if (usernameField) {
                        result.usernameFilled = this.fillField(usernameField, username);
                    } else {
                        result.errors.push('Username field not found');
                    }
                }
                
                // Fill password field
                if (password && loginFields.password.length > 0) {
                    const passwordField = document.querySelector('input[type="password"]');
                    if (passwordField) {
                        result.passwordFilled = this.fillField(passwordField, password);
                    } else {
                        result.errors.push('Password field not found');
                    }
                }
                
                result.success = result.usernameFilled || result.passwordFilled;
                
                // Auto-submit if requested and both fields were filled
                if (autoSubmit && result.usernameFilled && result.passwordFilled) {
                    const form = document.querySelector('form');
                    if (form) {
                        // Small delay to ensure values are processed
                        setTimeout(() => {
                            form.submit();
                            result.submitted = true;
                        }, 100);
                    }
                }
                
                return result;
            } catch (error) {
                result.errors.push(`Fill error: ${error.message}`);
                return result;
            }
        },
        
        /**
         * Get the element at a specific coordinate (for context menu)
         * @param {number} x - X coordinate
         * @param {number} y - Y coordinate
         * @returns {Object|null} Element information or null
         */
        getElementAtPosition: function(x, y) {
            try {
                const element = document.elementFromPoint(x, y);
                if (!element) {
                    return null;
                }
                
                // Check if it's a form field
                if (['input', 'textarea', 'select'].includes(element.tagName.toLowerCase())) {
                    return this._getInputInfo(element);
                }
                
                return null;
            } catch (error) {
                console.error('KeePassXC Bridge: Get element error:', error);
                return null;
            }
        },
        
        /**
         * Trigger appropriate events on an element after value change
         * @param {Element} element - The element to trigger events on
         */
        _triggerEvents: function(element) {
            const events = ['input', 'change', 'blur'];
            
            events.forEach(eventType => {
                const event = new Event(eventType, {
                    bubbles: true,
                    cancelable: true
                });
                element.dispatchEvent(event);
            });
            
            // Also trigger React-specific events if detected
            if (this._hasReact(element)) {
                this._triggerReactEvents(element);
            }
        },
        
        /**
         * Check if element is controlled by React
         * @param {Element} element - Element to check
         * @returns {boolean} True if React is detected
         */
        _hasReact: function(element) {
            // Check for React fiber properties
            const keys = Object.keys(element);
            return keys.some(key => key.startsWith('__reactInternalInstance') || key.startsWith('_reactInternalFiber'));
        },
        
        /**
         * Trigger React-specific events
         * @param {Element} element - Element to trigger events on
         */
        _triggerReactEvents: function(element) {
            // Create a more comprehensive event for React
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(element, element.value);
            
            const inputEvent = new Event('input', { bubbles: true });
            element.dispatchEvent(inputEvent);
        },
        
        /**
         * Clear all form fields
         * @returns {number} Number of fields cleared
         */
        clearAllFields: function() {
            let cleared = 0;
            document.querySelectorAll('input, textarea').forEach(input => {
                if (input.type !== 'hidden' && input.type !== 'submit' && input.type !== 'button') {
                    input.value = '';
                    this._triggerEvents(input);
                    cleared++;
                }
            });
            return cleared;
        },
        
        /**
         * Highlight form fields (for debugging/visualization)
         * @param {string} color - Highlight color
         */
        highlightFields: function(color = 'yellow') {
            document.querySelectorAll('input, textarea, select').forEach(input => {
                if (this._isVisible(input)) {
                    input.style.backgroundColor = color;
                    input.style.border = '2px solid red';
                }
            });
        },
        
        /**
         * Remove highlighting from form fields
         */
        removeHighlight: function() {
            document.querySelectorAll('input, textarea, select').forEach(input => {
                input.style.backgroundColor = '';
                input.style.border = '';
            });
        }
    };
    
    // Export for Node.js/CommonJS if available
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = window.KeePassXCBridge;
    }
    
    console.log('KeePassXC Bridge loaded successfully');
})();