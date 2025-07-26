"""
Utility functions for Creature Browser.
Contains various helper functions for timestamps, URLs, and certificates.
"""

import re
import socket
import ssl
import urllib.parse
import uuid
from datetime import datetime
from urllib.parse import urlparse

from creature_config import config as creature_config
import logging

logger = logging.getLogger(__name__)


# Firefox bookmarks format utilities
def generate_guid():
    """Generate a Firefox-compatible GUID."""
    return str(uuid.uuid4()).replace('-', '')[:12]


def datetime_to_firefox_timestamp(dt=None):
    """Convert datetime to Firefox timestamp (microseconds since Unix epoch)."""
    if dt is None:
        dt = datetime.now()
    elif isinstance(dt, str):
        # Parse ISO string if provided
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            dt = datetime.now()
    
    return int(dt.timestamp() * 1000000)


def firefox_timestamp_to_datetime(timestamp):
    """Convert Firefox timestamp to datetime."""
    try:
        # Firefox timestamps are in microseconds
        return datetime.fromtimestamp(timestamp / 1000000)
    except:
        return datetime.now()


def process_url_or_search(input_text):
    """Process user input to determine if it's a URL or search query.
    
    Args:
        input_text: User input from URL bar
        
    Returns:
        tuple: (url, is_search) where url is the final URL and is_search indicates if it's a search
    """
    if not input_text or not input_text.strip():
        return creature_config.general.home_page, False
    
    input_text = input_text.strip()
    
    # Check if it's already a complete URL with protocol
    if re.match(r'^https?://', input_text):
        return input_text, False
    
    # Check if it looks like a URL (has dot and no spaces, or is localhost/IP)
    url_patterns = [
        r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$',  # domain.com/path
        r'^localhost(:[0-9]+)?(/.*)?$',           # localhost:port/path
        r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(:[0-9]+)?(/.*)?$',  # IP:port/path
        r'^[a-zA-Z0-9.-]+(:[0-9]+)(/.*)?$',       # hostname:port/path (local network)
    ]
    
    for pattern in url_patterns:
        if re.match(pattern, input_text):
            # Add https:// prefix for proper URLs
            return f"https://{input_text}", False
    
    # Check if it starts with http/https but isn't complete (support local DNS)
    if input_text.startswith(('http://', 'https://')):
        return input_text, False
    
    # Otherwise, treat as search query
    search_engine = creature_config.search.default_engine
    search_url_template = getattr(creature_config.search, search_engine)
    search_url = search_url_template.replace('%s', urllib.parse.quote_plus(input_text))
    
    return search_url, True


def fetch_certificate_from_url(url_string):
    """Fetch SSL certificate from URL using Python SSL."""
    try:
        parsed_url = urlparse(url_string)
        if parsed_url.scheme != 'https':
            return None, "URL is not HTTPS"
        
        hostname = parsed_url.hostname
        port = parsed_url.port or 443
        
        logger.debug(f"Fetching certificate for {hostname}:{port}")
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # Get certificate in DER format
                cert_der = ssock.getpeercert(binary_form=True)
                # Get certificate info
                cert_info = ssock.getpeercert()
                
                return cert_der, cert_info
                
    except socket.timeout:
        return None, "Connection timed out"
    except socket.gaierror:
        return None, "Failed to resolve hostname"
    except ssl.SSLError as e:
        return None, f"SSL error: {str(e)}"
    except Exception as e:
        return None, f"Failed to fetch certificate: {str(e)}"