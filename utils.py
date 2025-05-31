from urllib.parse import urlparse, urljoin
import re


def is_valid_url(url):
    """Check if a URL is valid and has a proper scheme and netloc"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except:
        return False


def get_domain(url):
    """Extract the domain from a URL, removing www. prefix"""
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')


def is_external_url(base_domain, url):
    """Check if a URL is external to the base domain"""
    return get_domain(url) != base_domain


def normalize_url(url):
    """Normalize a URL by removing trailing slashes and fragments"""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    if not path:
        path = '/'
    
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    
    return normalized


def is_same_domain(url1, url2):
    """Check if two URLs belong to the same domain"""
    return get_domain(url1) == get_domain(url2)


def get_url_depth(base_url, url):
    """Calculate the depth of a URL relative to the base URL"""
    base_path = urlparse(base_url).path
    url_path = urlparse(url).path
    
    # Remove trailing slashes
    base_path = base_path.rstrip('/')
    url_path = url_path.rstrip('/')
    
    # If paths are the same, depth is 0
    if base_path == url_path:
        return 0
    
    # Count path segments
    base_segments = [s for s in base_path.split('/') if s]
    url_segments = [s for s in url_path.split('/') if s]
    
    # Find common prefix
    common_prefix_len = 0
    for i in range(min(len(base_segments), len(url_segments))):
        if base_segments[i] == url_segments[i]:
            common_prefix_len += 1
        else:
            break
    
    # Depth is the number of segments after the common prefix
    return len(url_segments) - common_prefix_len


def is_ignorable_url(url):
    """Check if a URL should be ignored (e.g., mailto, javascript, etc.)"""
    return url.startswith(('mailto:', 'tel:', 'javascript:', 'data:', '#')) or \
           url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar'))


def extract_domain_parts(domain):
    """Extract parts of a domain (e.g., 'sub.example.com' -> ['sub', 'example', 'com'])"""
    return domain.split('.')