"""
SSL certificate handling for Creature Browser.
Contains functions and classes for SSL certificate validation, parsing, and display.
"""

import json
import logging
import os
import socket
import ssl
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFormLayout, QHBoxLayout,
    QPushButton, QGroupBox, QMessageBox, QApplication
)

logger = logging.getLogger(__name__)


def export_certificate_to_file(cert_der, hostname):
    """Export certificate DER data to a temporary file."""
    try:
        # Create temporary file with .crt extension
        temp_fd, temp_path = tempfile.mkstemp(suffix=f'_{hostname}.crt', prefix='creature_cert_')
        
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        logger.debug(f"Certificate exported to: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.debug(f"Failed to export certificate: {e}")
        return None


def check_openssl_available():
    """Check if OpenSSL command-line tool is available."""
    try:
        result = subprocess.run(['openssl', 'version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.debug(f"OpenSSL available: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    logger.debug("OpenSSL not available")
    return False


def parse_certificate_with_openssl(cert_der):
    """Parse certificate using OpenSSL to get detailed information."""
    try:
        # Write certificate to temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.crt')
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        try:
            # Use OpenSSL to parse certificate details
            result = subprocess.run([
                'openssl', 'x509', '-in', temp_path, '-text', '-noout'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse the OpenSSL output
                cert_details = parse_openssl_output(result.stdout)
                logger.debug(f"Parsed certificate with OpenSSL: {len(cert_details)} fields")
                return cert_details
            else:
                logger.debug(f"OpenSSL parsing failed: {result.stderr}")
                return None
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        logger.debug(f"Failed to parse with OpenSSL: {e}")
        return None


def check_certificate_revocation(cert_der, hostname):
    """Check certificate revocation status using OCSP and CRL."""
    revocation_info = {
        'checked': False,
        'revoked': False,
        'method': None,
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Write certificate to temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.crt')
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        try:
            logger.debug(f"Checking certificate revocation for {hostname}")
            
            # First try OCSP check using OpenSSL
            logger.debug("Attempting OCSP check...")
            ocsp_result = check_ocsp_status(temp_path, hostname)
            
            if ocsp_result['checked']:
                revocation_info.update(ocsp_result)
                return revocation_info
            
            # If OCSP fails, try CRL check
            logger.debug("OCSP failed, attempting CRL check...")
            crl_result = check_crl_status(temp_path)
            
            if crl_result['checked']:
                revocation_info.update(crl_result)
                return revocation_info
            
            # If both fail, return with error info
            revocation_info['error'] = "Both OCSP and CRL checks failed"
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        logger.debug(f"Exception in revocation check: {e}")
        revocation_info['error'] = str(e)
    
    return revocation_info


def check_ocsp_status(cert_path, hostname):
    """Check OCSP status using OpenSSL."""
    ocsp_info = {
        'checked': False,
        'revoked': False,
        'method': 'OCSP',
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Try to get issuer certificate for OCSP check
        # This is a simplified approach - for production, you'd need the full chain
        result = subprocess.run([
            'openssl', 'x509', '-in', cert_path, '-noout', '-ocsp_uri'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            ocsp_url = result.stdout.strip()
            logger.debug(f"Found OCSP URL: {ocsp_url}")
            
            # For now, we'll indicate that OCSP is available but not perform the full check
            # Full OCSP checking requires the issuer certificate and is complex
            ocsp_info['status'] = 'OCSP available but not checked (requires issuer cert)'
            ocsp_info['checked'] = True
            ocsp_info['ocsp_url'] = ocsp_url
            
        else:
            ocsp_info['error'] = 'No OCSP URL found in certificate'
            
    except Exception as e:
        logger.debug(f"OCSP check failed: {e}")
        ocsp_info['error'] = str(e)
    
    return ocsp_info


def check_crl_status(cert_path):
    """Check CRL status using OpenSSL."""
    crl_info = {
        'checked': False,
        'revoked': False,
        'method': 'CRL',
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Get CRL distribution points from certificate
        result = subprocess.run([
            'openssl', 'x509', '-in', cert_path, '-noout', '-text'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            output = result.stdout
            # Look for CRL distribution points
            if 'CRL Distribution Points:' in output:
                # Extract CRL URLs (simplified)
                lines = output.split('\n')
                crl_urls = []
                in_crl_section = False
                
                for line in lines:
                    if 'CRL Distribution Points:' in line:
                        in_crl_section = True
                    elif in_crl_section and 'URI:' in line:
                        uri = line.split('URI:')[1].strip()
                        if uri.startswith('http'):
                            crl_urls.append(uri)
                    elif in_crl_section and line.strip() and not line.startswith(' '):
                        in_crl_section = False
                
                if crl_urls:
                    logger.debug(f"Found CRL URLs: {crl_urls}")
                    crl_info['status'] = f'CRL available but not checked (found {len(crl_urls)} distribution points)'
                    crl_info['checked'] = True
                    crl_info['crl_urls'] = crl_urls
                else:
                    crl_info['error'] = 'CRL Distribution Points found but no valid URLs'
            else:
                crl_info['error'] = 'No CRL Distribution Points found in certificate'
        else:
            crl_info['error'] = f'Failed to read certificate: {result.stderr}'
            
    except Exception as e:
        logger.debug(f"CRL check failed: {e}")
        crl_info['error'] = str(e)
    
    return crl_info


def parse_openssl_output(openssl_text):
    """Parse OpenSSL x509 text output into structured data."""
    logger.debug(f"Parsing OpenSSL output, length: {len(openssl_text)}")
    
    cert_details = {}
    lines = openssl_text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Key certificate fields
        if line.startswith('Version:'):
            cert_details['version'] = line.split(':', 1)[1].strip()
        elif line.startswith('Serial Number:'):
            # Handle multiline serial numbers
            serial = line.split(':', 1)[1].strip()
            # If serial is empty, look at next line
            if not serial and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Serial number is usually on the next line with hex format
                if next_line and not next_line.startswith(('Version:', 'Signature Algorithm:')):
                    serial = next_line
            cert_details['serial_number'] = serial
        elif line.startswith('Issuer:'):
            cert_details['issuer'] = line.split(':', 1)[1].strip()
        elif line.startswith('Subject:'):
            cert_details['subject'] = line.split(':', 1)[1].strip()
        elif 'Not Before:' in line:
            cert_details['not_before'] = line.split('Not Before:', 1)[1].strip()
        elif 'Not After :' in line or 'Not After:' in line:
            cert_details['not_after'] = line.split('Not After', 1)[1].split(':', 1)[1].strip()
        elif line.startswith('Public Key Algorithm:'):
            cert_details['public_key_algorithm'] = line.split(':', 1)[1].strip()
        elif 'Public-Key:' in line:
            # Extract key size
            if '(' in line and 'bit)' in line:
                key_size = line.split('(')[1].split(' bit)')[0]
                cert_details['key_size'] = f"{key_size} bits"
        elif line.startswith('Signature Algorithm:'):
            cert_details['signature_algorithm'] = line.split(':', 1)[1].strip()
        elif 'DNS:' in line:
            # Extract Subject Alternative Names
            if 'subject_alt_names' not in cert_details:
                cert_details['subject_alt_names'] = []
            # Parse DNS entries from SAN
            dns_entries = []
            parts = line.split('DNS:')
            for part in parts[1:]:  # Skip first empty part
                dns_name = part.split(',')[0].strip()
                if dns_name:
                    dns_entries.append(dns_name)
            cert_details['subject_alt_names'].extend(dns_entries)
    
    logger.debug(f"Parsed {len(cert_details)} certificate fields")
    return cert_details


class CertificateDetailsDialog(QDialog):
    """Dialog showing detailed SSL certificate information."""
    
    def __init__(self, ssl_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Certificate Details")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.setup_ui(ssl_info)
    
    def setup_ui(self, ssl_info):
        """Set up the certificate details UI."""
        layout = QVBoxLayout(self)
        
        # Security status header
        status_label = QLabel()
        if ssl_info.get('is_secure'):
            if ssl_info.get('certificate_valid'):
                status_label.setText("🔒 Secure Connection")
                status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
            else:
                status_label.setText("⚠️ Secure Connection with Certificate Issues")
                status_label.setStyleSheet("color: orange; font-weight: bold; font-size: 14px;")
        else:
            status_label.setText("🔓 Insecure Connection (HTTP)")
            status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        
        layout.addWidget(status_label)
        
        # Certificate information
        cert_info = ssl_info.get('certificate_info')
        if cert_info and cert_info.get('certificate_chain'):
            # Show certificate chain details
            for i, cert in enumerate(cert_info['certificate_chain']):
                cert_widget = self.create_certificate_widget(cert, i)
                layout.addWidget(cert_widget)
        elif ssl_info.get('is_secure'):
            # For valid HTTPS connections without error info
            info_widget = self.create_secure_connection_widget()
            layout.addWidget(info_widget)
        else:
            # HTTP connection
            info_label = QLabel("No SSL certificate - connection is not encrypted")
            info_label.setStyleSheet("color: red;")
            layout.addWidget(info_label)
        
        # Error information
        if ssl_info.get('errors'):
            error_widget = self.create_error_widget(ssl_info['errors'])
            layout.addWidget(error_widget)
        
        # Store ssl_info for export functionality
        self.ssl_info = ssl_info
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Export certificate button
        if ssl_info.get('is_secure'):
            export_button = QPushButton("Export Certificate")
            export_button.clicked.connect(self.export_certificate)
            button_layout.addWidget(export_button)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def create_certificate_widget(self, cert_details, index):
        """Create widget displaying certificate details."""
        group_box = QGroupBox(f"Certificate {index + 1}")
        layout = QFormLayout(group_box)
        
        layout.addRow("Subject:", QLabel(cert_details.get('subject', 'N/A')))
        layout.addRow("Issuer:", QLabel(cert_details.get('issuer', 'N/A')))
        layout.addRow("Valid From:", QLabel(cert_details.get('effective_date', 'N/A')))
        layout.addRow("Valid Until:", QLabel(cert_details.get('expiry_date', 'N/A')))
        layout.addRow("Self-signed:", QLabel('Yes' if cert_details.get('is_self_signed', False) else 'No'))
        layout.addRow("Serial Number:", QLabel(cert_details.get('serial_number', 'N/A')))
        layout.addRow("Version:", QLabel(cert_details.get('version', 'N/A')))
        
        return group_box
    
    def create_secure_connection_widget(self):
        """Create widget for secure HTTPS connections without certificate errors."""
        group_box = QGroupBox("Connection Information")
        layout = QFormLayout(group_box)
        
        # Add basic security information
        security_label = QLabel("✅ Connection is encrypted using HTTPS")
        security_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addRow(security_label)
        
        info_label = QLabel(
            "Your connection to this site is secure. Data sent between your browser "
            "and this website is encrypted and cannot be read by others."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-top: 10px;")
        layout.addRow(info_label)
        
        # Try to fetch and display detailed certificate information
        self.add_detailed_cert_info(layout)
        
        # Force layout update
        self.updateGeometry()
        self.update()
        
        return group_box
    
    def add_detailed_cert_info(self, layout):
        """Add detailed certificate information if available."""
        from utilities import fetch_certificate_from_url
        
        logger.debug("Fetching detailed certificate information...")
        
        # Get current URL from parent
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'web_view'):
            parent_tab = parent_tab.parent()
        
        if not parent_tab:
            logger.debug("Could not find parent tab with web_view")
            return
        
        current_url = parent_tab.web_view.url().toString()
        logger.debug(f"Current URL: {current_url}")
        
        # Check if OpenSSL is available for detailed parsing
        openssl_available = check_openssl_available()
        
        if openssl_available:
            try:
                # Fetch certificate
                result = fetch_certificate_from_url(current_url)
                
                if result[0] is not None:
                    cert_der, cert_info = result
                    
                    # Parse with OpenSSL for detailed info
                    openssl_details = parse_certificate_with_openssl(cert_der)
                    
                    # Check certificate revocation status
                    parsed_url = urlparse(current_url)
                    hostname = parsed_url.hostname
                    revocation_info = check_certificate_revocation(cert_der, hostname)
                    
                    # Update SSL status with revocation info
                    if hasattr(parent_tab, 'ssl_status'):
                        parent_tab.ssl_status['revocation_checked'] = revocation_info['checked']
                        parent_tab.ssl_status['revocation_status'] = revocation_info
                    
                    if openssl_details:
                        # Add detailed certificate information
                        cert_group = QGroupBox("Certificate Details")
                        cert_layout = QFormLayout(cert_group)
                        
                        # Add each field if available
                        fields_added = 0
                        if 'subject' in openssl_details and openssl_details['subject']:
                            cert_layout.addRow("Subject:", QLabel(openssl_details['subject']))
                            fields_added += 1
                        
                        if 'issuer' in openssl_details and openssl_details['issuer']:
                            cert_layout.addRow("Issuer:", QLabel(openssl_details['issuer']))
                            fields_added += 1
                        
                        if 'not_before' in openssl_details and openssl_details['not_before']:
                            cert_layout.addRow("Valid From:", QLabel(openssl_details['not_before']))
                            fields_added += 1
                        
                        if 'not_after' in openssl_details and openssl_details['not_after']:
                            cert_layout.addRow("Valid Until:", QLabel(openssl_details['not_after']))
                            fields_added += 1
                        
                        if 'serial_number' in openssl_details and openssl_details['serial_number']:
                            cert_layout.addRow("Serial Number:", QLabel(openssl_details['serial_number']))
                            fields_added += 1
                        
                        if 'signature_algorithm' in openssl_details and openssl_details['signature_algorithm']:
                            cert_layout.addRow("Signature Algorithm:", QLabel(openssl_details['signature_algorithm']))
                            fields_added += 1
                        
                        if 'public_key_algorithm' in openssl_details and openssl_details['public_key_algorithm']:
                            cert_layout.addRow("Public Key Algorithm:", QLabel(openssl_details['public_key_algorithm']))
                            fields_added += 1
                        
                        if 'key_size' in openssl_details and openssl_details['key_size']:
                            cert_layout.addRow("Key Size:", QLabel(openssl_details['key_size']))
                            fields_added += 1
                        
                        if 'subject_alt_names' in openssl_details and openssl_details['subject_alt_names']:
                            san_text = ', '.join(openssl_details['subject_alt_names'])
                            san_label = QLabel(san_text)
                            san_label.setWordWrap(True)
                            cert_layout.addRow("Subject Alt Names:", san_label)
                            fields_added += 1
                        
                        # Add revocation status
                        if revocation_info['checked']:
                            revocation_label = QLabel(revocation_info['status'])
                            if revocation_info['revoked']:
                                revocation_label.setStyleSheet("color: red; font-weight: bold;")
                            else:
                                revocation_label.setStyleSheet("color: green;")
                            cert_layout.addRow("Revocation Status:", revocation_label)
                            fields_added += 1
                        elif revocation_info['error']:
                            error_label = QLabel(f"Check failed: {revocation_info['error']}")
                            error_label.setStyleSheet("color: orange;")
                            error_label.setWordWrap(True)
                            cert_layout.addRow("Revocation Status:", error_label)
                            fields_added += 1
                        
                        if fields_added > 0:
                            layout.addRow(cert_group)
                            logger.debug(f"Added {fields_added} certificate fields to dialog")
                            return
                        
            except Exception as e:
                logger.debug(f"Exception in detailed cert info: {e}")
        
        # Fallback message
        fallback_msg = "Detailed certificate information "
        if openssl_available:
            fallback_msg += "could not be retrieved. Check debug output for details."
        else:
            fallback_msg += "requires OpenSSL command-line tools."
            
        limitation_label = QLabel(f"\n{fallback_msg}")
        limitation_label.setWordWrap(True)
        limitation_label.setStyleSheet("color: #888; font-size: 11px; font-style: italic; margin-top: 10px;")
        layout.addRow(limitation_label)
    
    def create_error_widget(self, errors):
        """Create widget displaying certificate errors."""
        group_box = QGroupBox("Certificate Errors")
        layout = QVBoxLayout(group_box)
        
        for error in errors:
            error_label = QLabel(f"Error: {error.get('description', 'Unknown error')}")
            error_label.setStyleSheet("color: red;")
            layout.addWidget(error_label)
        
        return group_box
    
    def export_certificate(self):
        """Export the SSL certificate to a temporary file and open it with system tools."""
        from utilities import fetch_certificate_from_url
        
        # We need to get the current URL from the parent browser tab
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'web_view'):
            parent_tab = parent_tab.parent()
        
        if not parent_tab:
            QMessageBox.warning(self, "Export Error", "Could not determine current URL")
            return
        
        current_url = parent_tab.web_view.url().toString()
        
        # Show progress message
        progress_msg = QMessageBox(self)
        progress_msg.setWindowTitle("Exporting Certificate")
        progress_msg.setText("Fetching certificate from server...")
        progress_msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress_msg.show()
        progress_msg.repaint()
        
        try:
            # Fetch certificate
            result = fetch_certificate_from_url(current_url)
            progress_msg.close()
            
            if result[0] is None:
                QMessageBox.warning(self, "Export Error", f"Failed to fetch certificate: {result[1]}")
                return
            
            cert_der, _ = result
            
            # Extract hostname from URL
            parsed_url = urlparse(current_url)
            hostname = parsed_url.hostname or 'unknown'
            
            # Export to file
            temp_path = export_certificate_to_file(cert_der, hostname)
            if not temp_path:
                QMessageBox.warning(self, "Export Error", "Failed to export certificate to file")
                return
            
            # Copy path to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(temp_path)
            
            # Try to open with system default viewer
            if os.name == 'nt':  # Windows
                os.startfile(temp_path)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.call(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', temp_path])
            
            QMessageBox.information(self, "Certificate Exported", 
                                  f"Certificate exported to:\n{temp_path}\n\n"
                                  "The path has been copied to clipboard.\n"
                                  "Opening with system default viewer...")
            
        except Exception as e:
            logger.error(f"Error exporting certificate: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export certificate: {str(e)}")